package com.verlumen.tradestream.backtesting.cli

import com.google.gson.GsonBuilder
import com.google.inject.Guice
import com.google.protobuf.Any
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.backtesting.BacktestRequest
import com.verlumen.tradestream.backtesting.BacktestResult
import com.verlumen.tradestream.backtesting.BacktestRunner
import com.verlumen.tradestream.backtesting.BacktestingModule
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategySpec
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
import kotlin.math.roundToInt

/**
 * Result returned by programmatic invocation of [BacktestCli].
 */
data class BacktestCliExecutionResult(
    val exitCode: Int,
    val stdout: String,
    val stderr: String,
    val backtestResult: BacktestResult? = null,
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
        const val DEFAULT_OUTPUT_FORMAT = "json"
        const val DEFAULT_INITIAL_CAPITAL = 10000.0

        @JvmStatic
        fun main(args: Array<String>) {
            val injector = Guice.createInjector(Ta4jModule.create(), BacktestingModule())
            val runner = injector.getInstance(BacktestRunner::class.java)
            val cli = BacktestCli(runner)
            val exitCode = cli.run(args, System.out, System.err)
            if (exitCode != 0) {
                System.exit(exitCode)
            }
        }

        fun createDefault(): BacktestCli {
            val injector = Guice.createInjector(Ta4jModule.create(), BacktestingModule())
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
                .description("Run a backtest on historical fixture market data and print a deterministic summary.")

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
            .addArgument("--fixtures", "-f")
            .type(String::class.java)
            .setDefault(DEFAULT_FIXTURE_PATH)
            .help("Path to market data fixture CSV file")

        parser
            .addArgument("--start")
            .type(String::class.java)
            .help("Optional start date/time (ISO-8601, e.g., 2024-01-01T00:00:00Z)")

        parser
            .addArgument("--end")
            .type(String::class.java)
            .help("Optional end date/time (ISO-8601, e.g., 2024-01-05T00:00:00Z)")

        parser
            .addArgument("--initial-capital", "-c")
            .type(Double::class.java)
            .setDefault(DEFAULT_INITIAL_CAPITAL)
            .help("Initial backtest capital (default: 10000.0)")

        parser
            .addArgument("--output", "-o")
            .type(String::class.java)
            .choices("json", "text")
            .setDefault(DEFAULT_OUTPUT_FORMAT)
            .help("Output format (json or text)")

        parser
            .addArgument("--params")
            .type(String::class.java)
            .help("Optional strategy parameter overrides (JSON string)")

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

        // Filter out "backtest" subcommand if passed as first argument (e.g., "tradestream backtest ...")
        val sanitizedArgs =
            if (args.isNotEmpty() && args[0] == "backtest") {
                args.copyOfRange(1, args.size)
            } else {
                args
            }

        if (sanitizedArgs.contains("-h") || sanitizedArgs.contains("--help")) {
            val writer = java.io.PrintWriter(out, true)
            parser.printHelp(writer)
            return 0
        }

        val ns: Namespace =
            try {
                parser.parseArgs(sanitizedArgs)
            } catch (e: net.sourceforge.argparse4j.helper.HelpScreenException) {
                return 0
            } catch (e: ArgumentParserException) {
                val printWriter = java.io.PrintWriter(err, true)
                parser.handleError(e, printWriter)
                return 1
            }

        val strategyInput = ns.getString("strategy") ?: DEFAULT_STRATEGY
        val instrument = ns.getString("instrument") ?: DEFAULT_INSTRUMENT
        val fixturesPath = ns.getString("fixtures") ?: DEFAULT_FIXTURE_PATH
        val outputFormat = ns.getString("output") ?: DEFAULT_OUTPUT_FORMAT
        val startFilter = ns.getString("start")
        val endFilter = ns.getString("end")

        // 1. Resolve strategy
        val strategySpecPair = findStrategySpec(strategyInput)
        if (strategySpecPair == null) {
            err.println("Error: Strategy '$strategyInput' is not supported.")
            err.println("Available strategies (${StrategySpecs.size()}):")
            StrategySpecs.getSupportedStrategyNames().take(15).forEach {
                err.println("  - $it")
            }
            err.println("  ... (${StrategySpecs.size() - 15} more)")
            return 2
        }

        val (canonicalStrategyName, spec) = strategySpecPair

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

        val candles = filterCandles(allCandles, startFilter, endFilter)
        if (candles.isEmpty()) {
            err.println("Error: No candles match the specified date range.")
            return 4
        }

        // 3. Build BacktestRequest with existing strategy
        val defaultParams = spec.strategyFactory.defaultParameters
        val strategyProto =
            Strategy
                .newBuilder()
                .setStrategyName(canonicalStrategyName)
                .setParameters(Any.pack(defaultParams))
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

        if (outputFormat.equals("text", ignoreCase = true)) {
            printTextSummary(out, canonicalStrategyName, instrument, periodStart, periodEnd, result)
        } else {
            printJsonSummary(out, canonicalStrategyName, instrument, periodStart, periodEnd, result)
        }

        return 0
    }

    private fun findStrategySpec(name: String): Pair<String, StrategySpec>? {
        val trimmed = name.trim()
        val normalized = trimmed.uppercase().replace("-", "_")

        if (StrategySpecs.isSupported(normalized)) {
            return normalized to StrategySpecs.getSpec(normalized)
        }

        val match =
            StrategySpecs.getSupportedStrategyNames().firstOrNull {
                it.equals(trimmed, ignoreCase = true) || it.equals(normalized, ignoreCase = true)
            }
        return match?.let { it to StrategySpecs.getSpec(it) }
    }

    private fun resolveFixtureFile(pathStr: String): File {
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

        val candles = mutableListOf<Candle>()
        for (i in 1 until lines.size) {
            val row = lines[i].split(",").map { it.trim() }
            if (row.size < 5) continue

            val timestamp = parseTimestampString(row[timeIdx])
            val open = row[openIdx].toDouble()
            val high = row[highIdx].toDouble()
            val low = row[lowIdx].toDouble()
            val close = row[closeIdx].toDouble()
            val volume = if (volIdx >= 0 && volIdx < row.size) row[volIdx].toDouble() else 0.0

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

    private fun parseTimestampString(raw: String): com.google.protobuf.Timestamp =
        try {
            val instant = Instant.parse(raw)
            Timestamps.fromMillis(instant.toEpochMilli())
        } catch (_: Exception) {
            val num = raw.toLong()
            if (num < 10_000_000_000L) {
                Timestamps.fromSeconds(num)
            } else {
                Timestamps.fromMillis(num)
            }
        }

    private fun formatTimestamp(ts: com.google.protobuf.Timestamp): String =
        Instant.ofEpochMilli(Timestamps.toMillis(ts)).toString()

    private fun filterCandles(
        candles: List<Candle>,
        startFilter: String?,
        endFilter: String?,
    ): List<Candle> {
        val startMillis = startFilter?.let { parseTimestampString(it).let { ts -> Timestamps.toMillis(ts) } }
        val endMillis = endFilter?.let { parseTimestampString(it).let { ts -> Timestamps.toMillis(ts) } }

        return candles.filter { candle ->
            val millis = Timestamps.toMillis(candle.timestamp)
            val afterStart = startMillis == null || millis >= startMillis
            val beforeEnd = endMillis == null || millis <= endMillis
            afterStart && beforeEnd
        }
    }

    private fun round(
        value: Double,
        decimals: Int,
    ): Double {
        if (!value.isFinite()) return 0.0
        val factor = 10.0.pow(decimals)
        return (value * factor).roundToInt() / factor
    }

    private fun formatTradeDuration(durationBars: Double): String {
        val rounded = round(durationBars, 1)
        return "$rounded bars"
    }

    private fun printJsonSummary(
        out: PrintStream,
        strategyName: String,
        instrument: String,
        start: String,
        end: String,
        result: BacktestResult,
    ) {
        val recommendation =
            if (result.strategyScore >= 0.5 || result.cumulativeReturn > 0.0) {
                "Strategy shows positive expectancy. Consider using."
            } else {
                "Strategy does not show positive expectancy. Consider optimization."
            }

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
                        "total_return_pct" to round(result.cumulativeReturn * 100.0, 2),
                        "annualized_return_pct" to round(result.annualizedReturn * 100.0, 2),
                        "sharpe_ratio" to round(result.sharpeRatio, 2),
                        "sortino_ratio" to round(result.sortinoRatio, 2),
                        "max_drawdown_pct" to round(result.maxDrawdown * 100.0, 2),
                        "win_rate" to round(result.winRate, 2),
                        "profit_factor" to round(result.profitFactor, 2),
                        "volatility" to round(result.volatility, 4),
                        "total_trades" to result.numberOfTrades,
                        "avg_trade_duration" to formatTradeDuration(result.averageTradeDuration),
                        "strategy_score" to round(result.strategyScore, 2),
                    ),
                "recommendation" to recommendation,
            )

        val gson = GsonBuilder().setPrettyPrinting().create()
        out.println(gson.toJson(jsonMap))
    }

    private fun printTextSummary(
        out: PrintStream,
        strategyName: String,
        instrument: String,
        start: String,
        end: String,
        result: BacktestResult,
    ) {
        val rec =
            if (result.strategyScore >= 0.5 || result.cumulativeReturn > 0.0) {
                "Strategy shows positive expectancy. Consider using."
            } else {
                "Strategy does not show positive expectancy. Consider optimization."
            }

        out.println("==================================================")
        out.println(" TradeStream Backtest Summary")
        out.println("==================================================")
        out.println("Strategy:           $strategyName")
        out.println("Instrument:         $instrument")
        out.println("Period:             $start to $end")
        out.println("--------------------------------------------------")
        out.println("Total Return:       ${round(result.cumulativeReturn * 100.0, 2)}%")
        out.println("Annualized Return:  ${round(result.annualizedReturn * 100.0, 2)}%")
        out.println("Sharpe Ratio:       ${round(result.sharpeRatio, 2)}")
        out.println("Sortino Ratio:      ${round(result.sortinoRatio, 2)}")
        out.println("Max Drawdown:       ${round(result.maxDrawdown * 100.0, 2)}%")
        out.println("Win Rate:           ${round(result.winRate * 100.0, 2)}%")
        out.println("Profit Factor:      ${round(result.profitFactor, 2)}")
        out.println("Volatility:         ${round(result.volatility, 4)}")
        out.println("Total Trades:       ${result.numberOfTrades}")
        out.println("Avg Trade Duration: ${formatTradeDuration(result.averageTradeDuration)}")
        out.println("Strategy Score:     ${round(result.strategyScore, 2)}")
        out.println("--------------------------------------------------")
        out.println("Recommendation:     $rec")
        out.println("==================================================")
    }
}
