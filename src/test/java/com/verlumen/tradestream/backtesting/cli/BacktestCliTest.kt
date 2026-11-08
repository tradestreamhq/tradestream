package com.verlumen.tradestream.backtesting.cli

import com.google.common.truth.Truth.assertThat
import com.google.gson.JsonParser
import com.verlumen.tradestream.backtesting.BacktestRequest
import com.verlumen.tradestream.backtesting.BacktestResult
import com.verlumen.tradestream.backtesting.BacktestRunner
import com.verlumen.tradestream.strategies.EmaMacdParameters
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class BacktestCliTest {
    @get:Rule
    val tempFolder = TemporaryFolder()

    private lateinit var cli: BacktestCli

    data class IndependentTrade(
        val entryBar: Int,
        val exitBar: Int,
        val entryPrice: Double,
        val exitPrice: Double,
    ) {
        val grossPnl: Double get() = exitPrice - entryPrice
        val durationBars: Double get() = (exitBar - entryBar).toDouble()
    }

    private fun loadCheckedInClosePrices(): List<Double> {
        val fixturePath = "fixtures/marketdata/btc_usd_1h.csv"
        val runfilesDir = System.getenv("RUNFILES_DIR") ?: System.getenv("TEST_SRCDIR")
        val file =
            if (runfilesDir != null) {
                val workspace = System.getenv("TEST_WORKSPACE") ?: "_main"
                val inWorkspace = java.io.File(runfilesDir, "$workspace/$fixturePath")
                if (inWorkspace.exists()) inWorkspace else java.io.File(runfilesDir, fixturePath)
            } else {
                java.io.File(fixturePath)
            }
        val lines = file.readLines().map { it.trim() }.filter { it.isNotEmpty() }
        val header = lines.first().split(",").map { it.trim().lowercase() }
        val closeIdx = header.indexOf("close")
        return lines.drop(1).map { row -> row.split(",")[closeIdx].trim().toDouble() }
    }

    private fun computeIndependentEma(values: List<Double>, startIndex: Int, period: Int): List<Double?> {
        val alpha = 2.0 / (period + 1)
        val ema = ArrayList<Double?>(values.size)
        for (i in 0 until startIndex) {
            ema.add(null)
        }
        var currentEma = values[startIndex]
        ema.add(currentEma)
        for (i in (startIndex + 1) until values.size) {
            currentEma = values[i] * alpha + currentEma * (1.0 - alpha)
            ema.add(currentEma)
        }
        return ema
    }

    private fun computeIndependentEmaMacdTrades(closes: List<Double>): List<IndependentTrade> {
        val ema12 = computeIndependentEma(closes, startIndex = 12, period = 12)
        val ema26 = computeIndependentEma(closes, startIndex = 26, period = 26)
        val macd = ArrayList<Double?>(closes.size)
        for (i in closes.indices) {
            val e12 = ema12[i]
            val e26 = ema26[i]
            if (e12 != null && e26 != null) {
                macd.add(e12 - e26)
            } else {
                macd.add(null)
            }
        }
        val signalValues = macd.drop(26).filterNotNull()
        val signalEma = computeIndependentEma(signalValues, startIndex = 0, period = 9)
        val signal = ArrayList<Double?>(closes.size)
        for (i in 0 until 26) {
            signal.add(null)
        }
        signal.addAll(signalEma)

        val trades = mutableListOf<IndependentTrade>()
        var entryBar: Int? = null

        for (i in 27 until closes.size) {
            val prevM = macd[i - 1]
            val currM = macd[i]
            val prevS = signal[i - 1]
            val currS = signal[i]
            if (prevM == null || currM == null || prevS == null || currS == null) continue

            // Ta4j CrossedUpIndicatorRule requires strictly less than on prev and strictly greater on curr
            val crossedOver = prevM < prevS && currM > currS
            // Ta4j CrossedDownIndicatorRule requires strictly greater than on prev and strictly less on curr
            val crossedUnder = prevM > prevS && currM < currS

            if (entryBar == null) {
                if (crossedOver) {
                    entryBar = i
                }
            } else {
                if (crossedUnder) {
                    trades.add(IndependentTrade(entryBar, i, closes[entryBar], closes[i]))
                    entryBar = null
                }
            }
        }
        return trades
    }

    @Before
    fun setUp() {
        cli = BacktestCli.createDefault()
    }

    @Test
    fun execute_withNoArgs_runsDefaultSmaRsiOnCheckedInFixture() {
        // Act - Run with no arguments (uses defaults: SMA_RSI, BTC/USD, json, checked-in fixture)
        val result = cli.execute(emptyArray())

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(result.stdout).asJsonObject
        assertThat(json.get("strategy").asString).isEqualTo("SMA_RSI")
        assertThat(json.get("instrument").asString).isEqualTo("BTC/USD")

        val period = json.getAsJsonObject("period")
        assertThat(period.get("start").asString).isEqualTo("2024-01-01T00:00:00Z")
        assertThat(period.get("end").asString).isEqualTo("2024-01-05T03:00:00Z")

        val results = json.getAsJsonObject("results")
        assertThat(results.keySet())
            .containsExactly(
                "initial_capital",
                "position_units",
                "gross_pnl_per_unit",
                "gross_pnl",
                "final_capital",
                "total_trades",
                "win_rate",
                "profit_factor",
                "avg_trade_duration_bars",
            )
        assertThat(results.get("initial_capital").asDouble).isEqualTo(10000.0)
        assertThat(results.get("position_units").asDouble).isEqualTo(0.237248)
        assertThat(results.get("gross_pnl_per_unit").asDouble).isEqualTo(0.0)
        assertThat(results.get("gross_pnl").asDouble).isEqualTo(0.0)
        assertThat(results.get("final_capital").asDouble).isEqualTo(10000.0)
        assertThat(results.get("total_trades").asInt).isEqualTo(0)
        assertThat(results.get("win_rate").asDouble).isEqualTo(0.0)
        assertThat(results.get("profit_factor").asDouble).isEqualTo(0.0)
        assertThat(results.get("avg_trade_duration_bars").asDouble).isEqualTo(0.0)
    }

    @Test
    fun execute_isDeterministic_sameInputOnCheckedInFixtureProducesIdenticalOutput() {
        // Arrange - Create two fresh separate CLI instances
        val cli1 = BacktestCli.createDefault()
        val cli2 = BacktestCli.createDefault()
        val args = arrayOf("--strategy", "EMA_MACD", "--output", "json")

        // Act - Run both instances on default checked-in fixture
        val run1 = cli1.execute(args)
        val run2 = cli2.execute(args)

        // Assert
        assertThat(run1.exitCode).isEqualTo(0)
        assertThat(run2.exitCode).isEqualTo(0)
        assertThat(run1.stdout).isNotEmpty()
        assertThat(run1.stdout).isEqualTo(run2.stdout)
        assertThat(run1.stderr).isEqualTo(run2.stderr)

        val json = JsonParser.parseString(run1.stdout).asJsonObject
        val results = json.getAsJsonObject("results")
        assertThat(results.get("gross_pnl_per_unit").asDouble).isEqualTo(100.0)
        assertThat(results.get("gross_pnl").asDouble).isEqualTo(23.72)
    }

    @Test
    fun execute_withCheckedInFixtureAndEmaMacd_returnsPinnedMetrics() {
        // Arrange - Independently derive expected trade metrics from checked-in CSV
        val closes = loadCheckedInClosePrices()
        val independentTrades = computeIndependentEmaMacdTrades(closes)
        assertThat(independentTrades).hasSize(1)
        val trade = independentTrades.first()
        assertThat(trade.entryBar).isEqualTo(58)
        assertThat(trade.exitBar).isEqualTo(67)
        assertThat(trade.entryPrice).isEqualTo(44050.0)
        assertThat(trade.exitPrice).isEqualTo(44150.0)
        val expectedGrossPnlPerUnit = 100.0
        val expectedDurationBars = 9.0
        val expectedTotalTrades = 1
        val expectedWinRate = 1.0
        assertThat(trade.grossPnl).isEqualTo(expectedGrossPnlPerUnit)
        assertThat(trade.durationBars).isEqualTo(expectedDurationBars)

        // Independently derive position-sized capital and PnL metrics from initial close price (42150.0)
        val initialClose = closes.first()
        val expectedPositionUnits = kotlin.math.round((10000.0 / initialClose) * 1_000_000.0) / 1_000_000.0
        val expectedGrossPnl = kotlin.math.round((10000.0 / initialClose) * trade.grossPnl * 100.0) / 100.0
        val expectedFinalCapital = kotlin.math.round((10000.0 + (10000.0 / initialClose) * trade.grossPnl) * 100.0) / 100.0
        assertThat(expectedPositionUnits).isEqualTo(0.237248)
        assertThat(expectedGrossPnl).isEqualTo(23.72)
        assertThat(expectedFinalCapital).isEqualTo(10023.72)

        val args = arrayOf("--strategy", "EMA_MACD", "--output", "json")

        // Act - JSON output
        val jsonResult = cli.execute(args)

        // Assert JSON structure and pinned values
        assertThat(jsonResult.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(jsonResult.stdout).asJsonObject
        assertThat(json.get("strategy").asString).isEqualTo("EMA_MACD")
        assertThat(json.get("instrument").asString).isEqualTo("BTC/USD")

        val period = json.getAsJsonObject("period")
        assertThat(period.get("start").asString).isEqualTo("2024-01-01T00:00:00Z")
        assertThat(period.get("end").asString).isEqualTo("2024-01-05T03:00:00Z")

        val results = json.getAsJsonObject("results")
        assertThat(results.keySet())
            .containsExactly(
                "initial_capital",
                "position_units",
                "gross_pnl_per_unit",
                "gross_pnl",
                "final_capital",
                "total_trades",
                "win_rate",
                "profit_factor",
                "avg_trade_duration_bars",
            )
        assertThat(results.get("initial_capital").asDouble).isEqualTo(10000.0)
        assertThat(results.get("position_units").asDouble).isEqualTo(expectedPositionUnits)
        assertThat(results.get("gross_pnl_per_unit").asDouble).isEqualTo(expectedGrossPnlPerUnit)
        assertThat(results.get("gross_pnl").asDouble).isEqualTo(expectedGrossPnl)
        assertThat(results.get("final_capital").asDouble).isEqualTo(expectedFinalCapital)
        assertThat(results.get("total_trades").asInt).isEqualTo(expectedTotalTrades)
        assertThat(results.get("win_rate").asDouble).isEqualTo(expectedWinRate)
        // Profit factor 1.0 is documented as a reviewed runner snapshot
        assertThat(results.get("profit_factor").asDouble).isEqualTo(1.0)
        assertThat(results.get("avg_trade_duration_bars").asDouble).isEqualTo(expectedDurationBars)

        assertThat(results.has("sharpe_ratio")).isFalse()
        assertThat(results.has("sortino_ratio")).isFalse()
        assertThat(results.has("strategy_score")).isFalse()
        assertThat(results.has("annualized_return")).isFalse()
        assertThat(results.has("max_drawdown")).isFalse()
        assertThat(results.has("volatility")).isFalse()

        assertThat(json.has("recommendation")).isFalse()
        assertThat(results.has("total_return_pct")).isFalse()

        // Act - Text output
        val textResult = cli.execute(arrayOf("--strategy", "EMA_MACD", "--output", "text"))

        // Assert Text output format and values
        assertThat(textResult.exitCode).isEqualTo(0)
        assertThat(textResult.stdout).contains("Initial Capital:    10000.0")
        assertThat(textResult.stdout).contains("Position Units:     0.237248")
        assertThat(textResult.stdout).contains("Gross PnL (1 unit): 100.0")
        assertThat(textResult.stdout).contains("Gross PnL:          23.72")
        assertThat(textResult.stdout).contains("Final Capital:      10023.72")
        assertThat(textResult.stdout).contains("Total Trades:       1")
        assertThat(textResult.stdout).contains("Win Rate:           1.0")
        assertThat(textResult.stdout).contains("Profit Factor:      1.0")
        assertThat(textResult.stdout).contains("Avg Trade Duration: 9.0 bars")
        assertThat(textResult.stdout).doesNotContain("Sharpe")
        assertThat(textResult.stdout).doesNotContain("Sortino")
        assertThat(textResult.stdout).doesNotContain("Score")
        assertThat(textResult.stdout).doesNotContain("Annualized")
        assertThat(textResult.stdout).doesNotContain("Drawdown")
        assertThat(textResult.stdout).doesNotContain("Volatility")
        assertThat(textResult.stdout).doesNotContain("%")
        assertThat(textResult.stdout).doesNotContain("Recommendation")
    }

    @Test
    fun execute_withDifferentInitialCapital_changesPositionSizeAndExecutionDerivedResults() {
        // Run 1: default 10000.0 (0.237248 BTC at initial close 42150.0)
        val res10k = cli.execute(arrayOf("--strategy", "EMA_MACD", "--output", "json", "--initial-capital", "10000"))
        assertThat(res10k.exitCode).isEqualTo(0)
        val json10k = JsonParser.parseString(res10k.stdout).asJsonObject.getAsJsonObject("results")
        assertThat(json10k.get("initial_capital").asDouble).isEqualTo(10000.0)
        assertThat(json10k.get("position_units").asDouble).isEqualTo(0.237248)
        assertThat(json10k.get("gross_pnl_per_unit").asDouble).isEqualTo(100.0)
        assertThat(json10k.get("gross_pnl").asDouble).isEqualTo(23.72)
        assertThat(json10k.get("final_capital").asDouble).isEqualTo(10023.72)

        // Run 2: 42150.0 (exactly 1.0 BTC at initial close 42150.0)
        val res42k = cli.execute(arrayOf("--strategy", "EMA_MACD", "--output", "json", "--initial-capital", "42150"))
        assertThat(res42k.exitCode).isEqualTo(0)
        val json42k = JsonParser.parseString(res42k.stdout).asJsonObject.getAsJsonObject("results")
        assertThat(json42k.get("initial_capital").asDouble).isEqualTo(42150.0)
        assertThat(json42k.get("position_units").asDouble).isEqualTo(1.0)
        assertThat(json42k.get("gross_pnl_per_unit").asDouble).isEqualTo(100.0)
        assertThat(json42k.get("gross_pnl").asDouble).isEqualTo(100.0)
        assertThat(json42k.get("final_capital").asDouble).isEqualTo(42250.0)

        // Run 3: -c 21075 (exactly 0.5 BTC at initial close 42150.0)
        val res21k = cli.execute(arrayOf("--strategy", "EMA_MACD", "--output", "json", "-c", "21075"))
        assertThat(res21k.exitCode).isEqualTo(0)
        val json21k = JsonParser.parseString(res21k.stdout).asJsonObject.getAsJsonObject("results")
        assertThat(json21k.get("initial_capital").asDouble).isEqualTo(21075.0)
        assertThat(json21k.get("position_units").asDouble).isEqualTo(0.5)
        assertThat(json21k.get("gross_pnl_per_unit").asDouble).isEqualTo(100.0)
        assertThat(json21k.get("gross_pnl").asDouble).isEqualTo(50.0)
        assertThat(json21k.get("final_capital").asDouble).isEqualTo(21125.0)
    }

    @Test
    fun execute_withNonPositiveInitialCapital_returnsExitCode2() {
        val zeroRes = cli.execute(arrayOf("--strategy", "EMA_MACD", "--initial-capital", "0"))
        assertThat(zeroRes.exitCode).isEqualTo(2)
        assertThat(zeroRes.stderr).contains("--initial-capital must be a finite positive number")

        val negRes = cli.execute(arrayOf("--strategy", "EMA_MACD", "--initial-capital", "-500"))
        assertThat(negRes.exitCode).isEqualTo(2)
        assertThat(negRes.stderr).contains("--initial-capital must be a finite positive number")
    }

    @Test
    fun execute_withCustomFakeRunner_delegatesAndMapsAllFields() {
        // Arrange - Test with custom runner double pinning all 9 well-defined fields
        var requestReceived: BacktestRequest? = null
        val fakeRunner =
            object : BacktestRunner {
                override fun runBacktest(request: BacktestRequest): BacktestResult {
                    requestReceived = request
                    return BacktestResult
                        .newBuilder()
                        .setCumulativeReturn(0.125)
                        .setAnnualizedReturn(0.45)
                        .setSharpeRatio(1.85)
                        .setSortinoRatio(2.10)
                        .setMaxDrawdown(0.082)
                        .setVolatility(0.02)
                        .setWinRate(0.62)
                        .setProfitFactor(1.95)
                        .setNumberOfTrades(47)
                        .setAverageTradeDuration(15.5)
                        .setStrategyScore(0.88)
                        .build()
                }
            }

        val customCli = BacktestCli(fakeRunner)
        val args = arrayOf("--strategy", "EMA_MACD", "--output", "json")

        // Act
        val result = customCli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        assertThat(requestReceived).isNotNull()
        assertThat(requestReceived!!.candlesCount).isEqualTo(100)

        val json = JsonParser.parseString(result.stdout).asJsonObject
        val metrics = json.getAsJsonObject("results")
        assertThat(metrics.keySet())
            .containsExactly(
                "initial_capital",
                "position_units",
                "gross_pnl_per_unit",
                "gross_pnl",
                "final_capital",
                "total_trades",
                "win_rate",
                "profit_factor",
                "avg_trade_duration_bars",
            )
        assertThat(metrics.get("initial_capital").asDouble).isEqualTo(10000.0)
        assertThat(metrics.get("position_units").asDouble).isEqualTo(0.237248)
        assertThat(metrics.get("gross_pnl_per_unit").asDouble).isEqualTo(0.12)
        assertThat(metrics.get("gross_pnl").asDouble).isEqualTo(0.03)
        assertThat(metrics.get("final_capital").asDouble).isEqualTo(10000.03)
        assertThat(metrics.get("total_trades").asInt).isEqualTo(47)
        assertThat(metrics.get("win_rate").asDouble).isEqualTo(0.62)
        assertThat(metrics.get("profit_factor").asDouble).isEqualTo(1.95)
        assertThat(metrics.get("avg_trade_duration_bars").asDouble).isEqualTo(15.5)
    }

    @Test
    fun execute_withNonFiniteValues_serializesAsJsonNullAndTextNA() {
        val nonFiniteRunner =
            object : BacktestRunner {
                override fun runBacktest(request: BacktestRequest): BacktestResult {
                    return BacktestResult
                        .newBuilder()
                        .setCumulativeReturn(Double.NaN)
                        .setWinRate(Double.POSITIVE_INFINITY)
                        .setProfitFactor(Double.NEGATIVE_INFINITY)
                        .setNumberOfTrades(0)
                        .setAverageTradeDuration(Double.NaN)
                        .build()
                }
            }
        val customCli = BacktestCli(nonFiniteRunner)

        // JSON check
        val jsonResult = customCli.execute(arrayOf("--strategy", "EMA_MACD", "--output", "json"))
        assertThat(jsonResult.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(jsonResult.stdout).asJsonObject
        val results = json.getAsJsonObject("results")
        assertThat(results.get("initial_capital").asDouble).isEqualTo(10000.0)
        assertThat(results.get("position_units").asDouble).isEqualTo(0.237248)
        assertThat(results.get("gross_pnl_per_unit").isJsonNull).isTrue()
        assertThat(results.get("gross_pnl").isJsonNull).isTrue()
        assertThat(results.get("final_capital").isJsonNull).isTrue()
        assertThat(results.get("win_rate").isJsonNull).isTrue()
        assertThat(results.get("profit_factor").isJsonNull).isTrue()
        assertThat(results.get("avg_trade_duration_bars").isJsonNull).isTrue()
        assertThat(results.get("total_trades").asInt).isEqualTo(0)

        // Text check
        val textResult = customCli.execute(arrayOf("--strategy", "EMA_MACD", "--output", "text"))
        assertThat(textResult.exitCode).isEqualTo(0)
        assertThat(textResult.stdout).contains("Initial Capital:    10000.0")
        assertThat(textResult.stdout).contains("Position Units:     0.237248")
        assertThat(textResult.stdout).contains("Gross PnL (1 unit): N/A")
        assertThat(textResult.stdout).contains("Gross PnL:          N/A")
        assertThat(textResult.stdout).contains("Final Capital:      N/A")
        assertThat(textResult.stdout).contains("Win Rate:           N/A")
        assertThat(textResult.stdout).contains("Profit Factor:      N/A")
        assertThat(textResult.stdout).contains("Avg Trade Duration: N/A bars")
        assertThat(textResult.stdout).contains("Total Trades:       0")
    }

    @Test
    fun execute_withValidParamsOverride_mutatesUnpackedParametersAndChangesExecution() {
        // Arrange - 1. Capture unpacked protobuf mutation with capturing runner
        var requestReceived: BacktestRequest? = null
        val capturingRunner =
            object : BacktestRunner {
                override fun runBacktest(request: BacktestRequest): BacktestResult {
                    requestReceived = request
                    return BacktestResult.getDefaultInstance()
                }
            }
        val customCli = BacktestCli(capturingRunner)
        val customArgs =
            arrayOf(
                "--strategy",
                "EMA_MACD",
                "--params",
                "{\"shortEmaPeriod\": 8, \"longEmaPeriod\": 21}",
            )

        // Act 1
        val customResult = customCli.execute(customArgs)

        // Assert 1
        assertThat(customResult.exitCode).isEqualTo(0)
        assertThat(requestReceived).isNotNull()
        val unpacked = requestReceived!!.strategy.parameters.unpack(EmaMacdParameters::class.java)
        assertThat(unpacked.shortEmaPeriod).isEqualTo(8)
        assertThat(unpacked.longEmaPeriod).isEqualTo(21)
        assertThat(unpacked.signalPeriod).isEqualTo(9)

        // Act 2 - Run real CLI on checked-in fixture with custom params over date slice
        val realArgs =
            arrayOf(
                "--strategy",
                "EMA_MACD",
                "--start",
                "2024-01-01",
                "--end",
                "2024-01-03",
                "--params",
                "{\"shortEmaPeriod\": 8, \"longEmaPeriod\": 21}",
            )
        val realResult = cli.execute(realArgs)

        // Assert 2
        assertThat(realResult.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(realResult.stdout).asJsonObject
        val results = json.getAsJsonObject("results")
        assertThat(results.get("avg_trade_duration_bars").asDouble).isEqualTo(7.0)
        assertThat(results.get("gross_pnl_per_unit").asDouble).isEqualTo(100.0)
    }

    @Test
    fun execute_withMalformedCsvRow_returnsExitCode4() {
        // Arrange - CSV with a row having fewer than 5 columns
        val malformedCsv = tempFolder.newFile("malformed_row.csv")
        malformedCsv.writeText(
            """
            timestamp,open,high,low,close,volume
            2024-01-01T00:00:00Z,42000.0,42200.0,41900.0,42150.0,150.0
            2024-01-01T01:00:00Z,42150.0,42300.0
            """.trimIndent(),
        )

        // Act
        val result =
            cli.execute(
                arrayOf(
                    "--strategy",
                    "EMA_MACD",
                    "--fixtures",
                    malformedCsv.absolutePath,
                ),
            )

        // Assert
        assertThat(result.exitCode).isEqualTo(4)
        assertThat(result.stderr).contains("Malformed CSV row")
    }

    @Test
    fun execute_withUnsortedCsvTimestamps_returnsExitCode4() {
        // Arrange - CSV with non-increasing timestamps
        val unsortedCsv = tempFolder.newFile("unsorted.csv")
        unsortedCsv.writeText(
            """
            timestamp,open,high,low,close,volume
            2024-01-01T01:00:00Z,42000.0,42200.0,41900.0,42150.0,150.0
            2024-01-01T00:00:00Z,42150.0,42300.0,42050.0,42200.0,120.0
            """.trimIndent(),
        )

        // Act
        val result =
            cli.execute(
                arrayOf(
                    "--strategy",
                    "EMA_MACD",
                    "--fixtures",
                    unsortedCsv.absolutePath,
                ),
            )

        // Assert
        assertThat(result.exitCode).isEqualTo(4)
        assertThat(result.stderr).contains("strictly increasing")
    }

    @Test
    fun execute_withCaseInsensitiveStrategyName_resolvesCorrectly() {
        // Arrange
        val args = arrayOf("--strategy", "ema_macd")

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(result.stdout).asJsonObject
        assertThat(json.get("strategy").asString).isEqualTo("EMA_MACD")
    }

    @Test
    fun execute_withLeadingSubcommand_stripsSubcommandAndRuns() {
        // Arrange
        val args = arrayOf("backtest", "--strategy", "EMA_MACD")

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(result.stdout).asJsonObject
        assertThat(json.get("strategy").asString).isEqualTo("EMA_MACD")
    }

    @Test
    fun execute_withUnsupportedStrategy_returnsErrorCodeAndListsStrategies() {
        // Arrange
        val args = arrayOf("--strategy", "DEFINITELY_UNKNOWN_STRATEGY_XYZ")

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(2)
        assertThat(result.stderr).contains("is not supported")
        assertThat(result.stderr).contains("Available strategies")
    }

    @Test
    fun execute_withMissingFixtureFile_returnsErrorCode() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "EMA_MACD",
                "--fixtures",
                "/tmp/non_existent_file_12345.csv",
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(3)
        assertThat(result.stderr).contains("Fixture file not found")
    }

    @Test
    fun execute_withHelpFlag_returnsZeroWithHelpOutput() {
        // Arrange
        val args = arrayOf("--help")

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        assertThat(result.stdout).contains("tradestream backtest")
        assertThat(result.stdout).contains("--initial-capital")
        assertThat(result.stdout).contains("--strategy")
        assertThat(result.stdout).contains("--fixtures")
    }

    @Test
    fun execute_withDateRange_filtersCandlesCorrectly() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "EMA_MACD",
                "--start",
                "2024-01-01",
                "--end",
                "2024-01-02",
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(result.stdout).asJsonObject
        val period = json.getAsJsonObject("period")
        assertThat(period.get("start").asString).isEqualTo("2024-01-01T00:00:00Z")
        assertThat(period.get("end").asString).isEqualTo("2024-01-02T23:00:00Z")
    }

    @Test
    fun execute_withMalformedDate_returnsExitCode2() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "EMA_MACD",
                "--start",
                "invalid-date-format",
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(2)
        assertThat(result.stderr).contains("Malformed date/time string")
    }

    @Test
    fun execute_withStartAfterEnd_returnsExitCode2() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "EMA_MACD",
                "--start",
                "2024-01-02",
                "--end",
                "2024-01-01",
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(2)
        assertThat(result.stderr).contains("cannot be after end date")
    }

    @Test
    fun execute_withInvalidParamsJson_returnsExitCode2() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "EMA_MACD",
                "--params",
                "{\"unknownField\": 123}",
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(2)
        assertThat(result.stderr).contains("Invalid --params JSON")
    }
}
