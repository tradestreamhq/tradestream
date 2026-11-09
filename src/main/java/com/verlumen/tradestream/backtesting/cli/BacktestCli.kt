package com.verlumen.tradestream.backtesting.cli

import com.google.gson.GsonBuilder
import com.google.protobuf.Any
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.backtesting.BacktestRequest
import com.verlumen.tradestream.backtesting.BacktestResult
import com.verlumen.tradestream.backtesting.BacktestRunner
import com.verlumen.tradestream.backtesting.BacktestingModule
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategySpecs
import com.verlumen.tradestream.ta4j.Ta4jModule
import net.sourceforge.argparse4j.ArgumentParsers
import net.sourceforge.argparse4j.inf.ArgumentParser
import net.sourceforge.argparse4j.inf.ArgumentParserException
import net.sourceforge.argparse4j.inf.Namespace
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.PrintStream
import java.time.Instant
import kotlin.math.pow
import kotlin.math.round

/**
 * Result returned by programmatic invocation of [BacktestCli].
 */
data class BacktestCliExecutionResult(
    val exitCode: Int,
    val stdout: String,
    val stderr: String,
)

/**
 * CLI Backtest Executor for Strategy Evaluation.
 *
 * Provides a minimal, deterministic command-line interface to run existing
 * Ta4j trading strategies on checked-in fixture market data.
 */
class BacktestCli(
    private val backtestRunner: BacktestRunner,
) {
    companion object {
        const val DEFAULT_FIXTURE_PATH = "fixtures/marketdata/btc_usd_1h.csv"
        const val DEFAULT_STRATEGY = "SMA_RSI"
        const val DEFAULT_INSTRUMENT = "BTC/USD"
        const val DEFAULT_INITIAL_CAPITAL = 10000.0

        @JvmStatic
        fun main(args: Array<String>) {
            val exitCode = createDefault().run(args, System.out, System.err)
            if (exitCode != 0) {
                System.exit(exitCode)
            }
        }

        fun createDefault(): BacktestCli {
            val injector = com.google.inject.Guice.createInjector(Ta4jModule.create(), BacktestingModule())
            val runner = injector.getInstance(BacktestRunner::class.java)
            return BacktestCli(runner)
        }
    }

    private fun createArgumentParser(): ArgumentParser {
        val parser =
            ArgumentParsers
                .newFor("tradestream backtest")
                .build()
                .defaultHelp(true)
                .description(
                    "Run a deterministic backtest on fixture CSV market data (fixture-only, long-only, 1-unit runner trades scaled by position_units = initial_capital / first filtered close; closed-trade gross P&L only, no open-position valuation, no compounding/cash constraint; win_rate, profit_factor (gross_profit / |gross_loss|), and avg_trade_duration_bars are null when undefined: 0 closed trades, or 0 gross loss for profit_factor).",
                )

        parser
            .addArgument("--strategy", "-s")
            .type(String::class.java)
            .setDefault(DEFAULT_STRATEGY)
            .help("Strategy to evaluate (e.g., SMA_RSI, EMA_MACD, MOMENTUM_PINBALL)")

        parser
            .addArgument("--instrument", "-i")
            .type(String::class.java)
            .setDefault(DEFAULT_INSTRUMENT)
            .help("Trading pair / instrument symbol (e.g., BTC/USD)")

        parser
            .addArgument("--initial-capital", "-c")
            .type(Double::class.java)
            .setDefault(DEFAULT_INITIAL_CAPITAL)
            .help(
                "Initial capital in quote currency used to size constant position_units = initial_capital / first filtered close; final_capital = initial_capital + gross_pnl from closed trades only (default: 10000.0)",
            )

        parser
            .addArgument("--fixtures", "-f")
            .type(String::class.java)
            .setDefault(DEFAULT_FIXTURE_PATH)
            .help("Path to market data fixture CSV file")

        parser
            .addArgument("--start")
            .type(String::class.java)
            .help("Optional start timestamp (ISO-8601 instant, e.g., 2024-01-01T00:00:00Z)")

        parser
            .addArgument("--end")
            .type(String::class.java)
            .help("Optional end timestamp (ISO-8601 instant, e.g., 2024-01-05T00:00:00Z)")

        return parser
    }

    /**
     * Executes the CLI with captured stdout and stderr for testing and programmatic use.
     */
    fun execute(args: Array<String>): BacktestCliExecutionResult {
        val outBytes = ByteArrayOutputStream()
        val errBytes = ByteArrayOutputStream()
        val outPrint = PrintStream(outBytes)
        val errPrint = PrintStream(errBytes)

        val exitCode = run(args, outPrint, errPrint)
        outPrint.flush()
        errPrint.flush()

        return BacktestCliExecutionResult(
            exitCode = exitCode,
            stdout = outBytes.toString(Charsets.UTF_8),
            stderr = errBytes.toString(Charsets.UTF_8),
        )
    }

    /**
     * Runs the CLI with given arguments and streams.
     */
    fun run(
        args: Array<String>,
        out: PrintStream,
        err: PrintStream,
    ): Int {
        val parser = createArgumentParser()

        if (args.contains("-h") || args.contains("--help")) {
            val writer = java.io.PrintWriter(out, true)
            parser.printHelp(writer)
            return 0
        }

        val ns: Namespace =
            try {
                parser.parseArgs(args)
            } catch (e: net.sourceforge.argparse4j.helper.HelpScreenException) {
                return 0
            } catch (e: ArgumentParserException) {
                val printWriter = java.io.PrintWriter(err, true)
                parser.handleError(e, printWriter)
                return 1
            }

        val strategyInput = ns.getString("strategy") ?: DEFAULT_STRATEGY
        val instrument = ns.getString("instrument") ?: DEFAULT_INSTRUMENT
        val initialCapital = ns.getDouble("initial_capital") ?: DEFAULT_INITIAL_CAPITAL
        if (!initialCapital.isFinite() || initialCapital <= 0.0) {
            err.println("Error: --initial-capital must be a finite positive number, got $initialCapital")
            return 2
        }
        val fixturesPath = ns.getString("fixtures") ?: DEFAULT_FIXTURE_PATH
        val startFilter = ns.getString("start")
        val endFilter = ns.getString("end")

        // 1. Resolve strategy
        if (!StrategySpecs.isSupported(strategyInput)) {
            err.println("Error: Strategy '$strategyInput' is not supported.")
            err.println("Available strategies (${StrategySpecs.size()}):")
            for (s in StrategySpecs.getSupportedStrategyNames().sorted().take(15)) {
                err.println("  - $s")
            }
            if (StrategySpecs.size() > 15) {
                err.println("  ... (${StrategySpecs.size() - 15} more)")
            }
            return 2
        }

        val spec = StrategySpecs.getSpec(strategyInput)

        // 2. Load and filter candle fixtures
        val fixtureFile = resolveFixtureFile(fixturesPath)
        if (!fixtureFile.exists()) {
            err.println("Error: Fixture file not found: ${fixtureFile.absolutePath}")
            return 3
        }

        val allCandles =
            try {
                parseCandlesFromCsv(fixtureFile, instrument)
            } catch (e: Exception) {
                err.println("Error parsing fixture file: ${e.message}")
                return 4
            }

        if (allCandles.isEmpty()) {
            err.println("Error: Fixture file contains no candles.")
            return 4
        }

        val candles =
            try {
                filterCandles(allCandles, startFilter, endFilter)
            } catch (e: IllegalArgumentException) {
                err.println("Error: ${e.message}")
                return 2
            }

        if (candles.isEmpty()) {
            err.println("Error: No candles match the specified date range ($startFilter to $endFilter).")
            return 2
        }

        // 3. Build BacktestRequest with strategy parameters
        val strategyProto =
            Strategy
                .newBuilder()
                .setStrategyName(strategyInput)
                .setParameters(Any.pack(spec.strategyFactory.defaultParameters))
                .build()

        val request =
            BacktestRequest
                .newBuilder()
                .addAllCandles(candles)
                .setStrategy(strategyProto)
                .build()

        // 4. Run Backtest
        val result: BacktestResult =
            try {
                backtestRunner.runBacktest(request)
            } catch (e: Exception) {
                err.println("Error executing backtest: ${e.message}")
                return 5
            }

        // 5. Format and print output
        val periodStart = formatTimestamp(candles.first().timestamp)
        val periodEnd = formatTimestamp(candles.last().timestamp)
        val initialClose = candles.first().close

        printJsonSummary(out, strategyInput, instrument, periodStart, periodEnd, initialCapital, initialClose, result)
        return 0
    }

    internal fun resolveFixtureFile(pathStr: String): File {
        val file = File(pathStr)
        if (file.exists()) {
            return file
        }

        // Check relative to Bazel test/runfiles environment
        val runfilesDir = System.getenv("RUNFILES_DIR") ?: System.getenv("TEST_SRCDIR")
        if (runfilesDir != null) {
            val workspace = System.getenv("TEST_WORKSPACE") ?: "_main"
            val inWorkspace = File(runfilesDir, "$workspace/$pathStr")
            if (inWorkspace.exists()) {
                return inWorkspace
            }
            val direct = File(runfilesDir, pathStr)
            if (direct.exists()) {
                return direct
            }
        }

        return file
    }

    private fun parseCandlesFromCsv(
        file: File,
        instrument: String,
    ): List<Candle> {
        val lines = file.readLines().map { it.trim() }.filter { it.isNotEmpty() }
        require(lines.size > 1) { "Fixture CSV must contain a header and at least one row" }

        val header = lines.first().split(",").map { it.trim().lowercase() }
        val timeIdx = header.indexOfFirst { it == "timestamp" || it == "time" || it == "date" }
        val openIdx = header.indexOf("open")
        val highIdx = header.indexOf("high")
        val lowIdx = header.indexOf("low")
        val closeIdx = header.indexOf("close")
        val volIdx = header.indexOfFirst { it == "volume" || it == "vol" }

        require(timeIdx >= 0 && openIdx >= 0 && highIdx >= 0 && lowIdx >= 0 && closeIdx >= 0) {
            "CSV header must contain timestamp/time, open, high, low, and close columns"
        }

        val requiredCols = maxOf(timeIdx, openIdx, highIdx, lowIdx, closeIdx, volIdx) + 1
        val candles = mutableListOf<Candle>()
        var prevMillis: Long? = null

        for (i in 1 until lines.size) {
            val row = lines[i].split(",").map { it.trim() }
            if (row.size < requiredCols) {
                throw IllegalArgumentException(
                    "Malformed CSV row at line ${i + 1}: expected at least $requiredCols columns, got ${row.size}",
                )
            }

            val timestamp = parseTimestampString(row[timeIdx])
            val currentMillis = Timestamps.toMillis(timestamp)
            require(prevMillis == null || currentMillis > prevMillis) {
                "CSV timestamps must be strictly increasing at line ${i + 1}"
            }
            prevMillis = currentMillis

            val open = row[openIdx].toDouble()
            val high = row[highIdx].toDouble()
            val low = row[lowIdx].toDouble()
            val close = row[closeIdx].toDouble()
            val volume = if (volIdx >= 0 && volIdx < row.size) row[volIdx].toDouble() else 0.0

            require(
                open.isFinite() && open > 0.0 &&
                    high.isFinite() && high > 0.0 &&
                    low.isFinite() && low > 0.0 &&
                    close.isFinite() && close > 0.0,
            ) {
                "CSV OHLC prices must be finite positive numbers at line ${i + 1}"
            }

            candles.add(
                Candle
                    .newBuilder()
                    .setTimestamp(timestamp)
                    .setOpen(open)
                    .setHigh(high)
                    .setLow(low)
                    .setClose(close)
                    .setVolume(volume)
                    .setCurrencyPair(instrument)
                    .build(),
            )
        }
        return candles
    }

    private fun parseFilterTimestamp(raw: String): Long {
        return try {
            Instant.parse(raw.trim()).toEpochMilli()
        } catch (e: Exception) {
            throw IllegalArgumentException("Malformed ISO-8601 timestamp: '$raw'. Expected e.g. 2024-01-01T00:00:00Z")
        }
    }

    private fun parseTimestampString(raw: String): com.google.protobuf.Timestamp =
        Timestamps.fromMillis(Instant.parse(raw.trim()).toEpochMilli())

    private fun formatTimestamp(ts: com.google.protobuf.Timestamp): String =
        Instant.ofEpochMilli(Timestamps.toMillis(ts)).toString()

    private fun filterCandles(
        candles: List<Candle>,
        startFilter: String?,
        endFilter: String?,
    ): List<Candle> {
        val startMillis = startFilter?.let { parseFilterTimestamp(it) }
        val endMillis = endFilter?.let { parseFilterTimestamp(it) }

        if (startMillis != null && endMillis != null && startMillis > endMillis) {
            throw IllegalArgumentException(
                "Start date ($startFilter) cannot be after end date ($endFilter)",
            )
        }

        return candles.filter { candle ->
            val millis = Timestamps.toMillis(candle.timestamp)
            val afterStart = startMillis == null || millis >= startMillis
            val beforeEnd = endMillis == null || millis <= endMillis
            afterStart && beforeEnd
        }
    }

    private fun roundFinite(
        value: Double,
        decimals: Int,
    ): Double? {
        if (!value.isFinite()) return null
        val factor = 10.0.pow(decimals)
        val scaled = value * factor
        if (!scaled.isFinite()) return null
        val rounded = round(scaled) / factor
        return if (rounded.isFinite()) rounded else null
    }

    private fun printJsonSummary(
        out: PrintStream,
        strategyName: String,
        instrument: String,
        start: String,
        end: String,
        initialCapital: Double,
        initialClose: Double,
        result: BacktestResult,
    ) {
        val positionUnits = initialCapital / initialClose
        val grossPnlPerUnit = result.cumulativeReturn
        val grossPnl = positionUnits * grossPnlPerUnit
        val finalCapital = initialCapital + grossPnl

        val jsonMap =
            linkedMapOf(
                "strategy" to strategyName,
                "instrument" to instrument,
                "period" to
                    linkedMapOf(
                        "start" to start,
                        "end" to end,
                    ),
                "results" to
                    linkedMapOf(
                        "initial_capital" to roundFinite(initialCapital, 2),
                        "position_units" to roundFinite(positionUnits, 6),
                        "gross_pnl_per_unit" to roundFinite(grossPnlPerUnit, 2),
                        "gross_pnl" to roundFinite(grossPnl, 2),
                        "final_capital" to roundFinite(finalCapital, 2),
                        "total_trades" to result.numberOfTrades,
                        "win_rate" to if (result.numberOfTrades > 0) roundFinite(result.winRate, 4) else null,
                        "profit_factor" to if (result.numberOfTrades > 0) roundFinite(result.profitFactor, 4) else null,
                        "avg_trade_duration_bars" to
                            if (result.numberOfTrades > 0) roundFinite(result.averageTradeDuration, 1) else null,
                    ),
            )

        val gson = GsonBuilder().serializeNulls().setPrettyPrinting().create()
        out.println(gson.toJson(jsonMap))
    }
}
