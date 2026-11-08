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
import java.io.File

@RunWith(JUnit4::class)
class BacktestCliTest {
    @get:Rule
    val tempFolder = TemporaryFolder()

    private lateinit var cli: BacktestCli

    @Before
    fun setUp() {
        cli = BacktestCli.createDefault()
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
    }

    @Test
    fun execute_withCheckedInFixtureAndEmaMacd_returnsPinnedMetrics() {
        // Arrange
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
        assertThat(results.get("gross_pnl_per_unit").asDouble).isEqualTo(100.0)
        assertThat(results.get("annualized_return").isJsonNull).isTrue()
        assertThat(results.get("sharpe_ratio").asDouble).isEqualTo(28282.0)
        assertThat(results.get("sortino_ratio").asDouble).isEqualTo(496.58)
        assertThat(results.get("max_drawdown").asDouble).isEqualTo(0.0582)
        assertThat(results.get("volatility").asDouble).isEqualTo(0.0035)
        assertThat(results.get("win_rate").asDouble).isEqualTo(1.0)
        assertThat(results.get("profit_factor").asDouble).isEqualTo(1.0)
        assertThat(results.get("total_trades").asInt).isEqualTo(1)
        assertThat(results.get("avg_trade_duration_bars").asDouble).isEqualTo(9.0)
        assertThat(results.get("strategy_score").asDouble).isEqualTo(0.94)

        assertThat(json.has("recommendation")).isFalse()
        assertThat(results.has("total_return_pct")).isFalse()
        assertThat(results.has("initial_capital")).isFalse()

        // Act - Text output
        val textResult = cli.execute(arrayOf("--strategy", "EMA_MACD", "--output", "text"))

        // Assert Text output format and values
        assertThat(textResult.exitCode).isEqualTo(0)
        assertThat(textResult.stdout).contains("Gross PnL (1 unit): 100.0")
        assertThat(textResult.stdout).contains("Annualized Return:  N/A")
        assertThat(textResult.stdout).contains("Max Drawdown:       0.0582")
        assertThat(textResult.stdout).contains("Win Rate:           1.0")
        assertThat(textResult.stdout).contains("Total Trades:       1")
        assertThat(textResult.stdout).contains("Avg Trade Duration: 9.0 bars")
        assertThat(textResult.stdout).doesNotContain("%")
        assertThat(textResult.stdout).doesNotContain("Recommendation")
    }

    @Test
    fun execute_withCustomFakeRunner_delegatesAndMapsAllFields() {
        // Arrange - Test with custom runner double pinning all 11 fields
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
        assertThat(metrics.get("gross_pnl_per_unit").asDouble).isEqualTo(0.12)
        assertThat(metrics.get("annualized_return").asDouble).isEqualTo(0.45)
        assertThat(metrics.get("sharpe_ratio").asDouble).isEqualTo(1.85)
        assertThat(metrics.get("sortino_ratio").asDouble).isEqualTo(2.1)
        assertThat(metrics.get("max_drawdown").asDouble).isEqualTo(0.082)
        assertThat(metrics.get("volatility").asDouble).isEqualTo(0.02)
        assertThat(metrics.get("win_rate").asDouble).isEqualTo(0.62)
        assertThat(metrics.get("profit_factor").asDouble).isEqualTo(1.95)
        assertThat(metrics.get("total_trades").asInt).isEqualTo(47)
        assertThat(metrics.get("avg_trade_duration_bars").asDouble).isEqualTo(15.5)
        assertThat(metrics.get("strategy_score").asDouble).isEqualTo(0.88)
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
