package com.verlumen.tradestream.backtesting.cli

import com.google.common.truth.Truth.assertThat
import com.google.gson.JsonParser
import com.verlumen.tradestream.backtesting.BacktestRequest
import com.verlumen.tradestream.backtesting.BacktestResult
import com.verlumen.tradestream.backtesting.BacktestRunner
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
    private lateinit var fixtureFile: File

    @Before
    fun setUp() {
        cli = BacktestCli.createDefault()

        // Create a localized fixture file in temp folder for hermetic testing
        fixtureFile = tempFolder.newFile("sample_btc_usd.csv")
        fixtureFile.writeText(
            """
            timestamp,open,high,low,close,volume
            2024-01-01T00:00:00Z,42000.0,42200.0,41900.0,42150.0,150.0
            2024-01-01T01:00:00Z,42150.0,42300.0,42050.0,42200.0,120.0
            2024-01-01T02:00:00Z,42200.0,42250.0,41950.0,42000.0,110.0
            2024-01-01T03:00:00Z,42000.0,42100.0,41800.0,41850.0,135.0
            2024-01-01T04:00:00Z,41850.0,42000.0,41700.0,41900.0,95.0
            2024-01-01T05:00:00Z,41900.0,42150.0,41850.0,42100.0,105.0
            2024-01-01T06:00:00Z,42100.0,42200.0,42000.0,42050.0,80.0
            2024-01-01T07:00:00Z,42050.0,42150.0,41900.0,41950.0,90.0
            2024-01-01T08:00:00Z,41950.0,42050.0,41800.0,41820.0,115.0
            2024-01-01T09:00:00Z,41820.0,41900.0,41650.0,41700.0,140.0
            2024-01-01T10:00:00Z,41700.0,41750.0,41400.0,41450.0,180.0
            2024-01-01T11:00:00Z,41450.0,41500.0,41100.0,41150.0,220.0
            2024-01-01T12:00:00Z,41150.0,41200.0,40800.0,40850.0,310.0
            2024-01-01T13:00:00Z,40850.0,40900.0,40400.0,40450.0,420.0
            2024-01-01T14:00:00Z,40450.0,40600.0,40100.0,40150.0,480.0
            2024-01-01T15:00:00Z,40150.0,40300.0,39800.0,39900.0,550.0
            2024-01-01T16:00:00Z,39900.0,40200.0,39750.0,40100.0,510.0
            2024-01-01T17:00:00Z,40100.0,40450.0,40000.0,40400.0,390.0
            2024-01-01T18:00:00Z,40400.0,40700.0,40300.0,40650.0,340.0
            2024-01-01T19:00:00Z,40650.0,41000.0,40550.0,40950.0,310.0
            2024-01-01T20:00:00Z,40950.0,41200.0,40800.0,41100.0,260.0
            2024-01-01T21:00:00Z,41100.0,41300.0,40950.0,41250.0,210.0
            2024-01-01T22:00:00Z,41250.0,41450.0,41150.0,41400.0,190.0
            2024-01-01T23:00:00Z,41400.0,41600.0,41300.0,41550.0,175.0
            2024-01-02T00:00:00Z,41550.0,41750.0,41450.0,41700.0,160.0
            2024-01-02T01:00:00Z,41700.0,41850.0,41600.0,41800.0,140.0
            2024-01-02T02:00:00Z,41800.0,42000.0,41750.0,41950.0,150.0
            2024-01-02T03:00:00Z,41950.0,42100.0,41850.0,42050.0,130.0
            2024-01-02T04:00:00Z,42050.0,42250.0,41950.0,42200.0,145.0
            2024-01-02T05:00:00Z,42200.0,42350.0,42100.0,42300.0,155.0
            """.trimIndent(),
        )
    }

    @Test
    fun execute_isDeterministic_sameInputProducesIdenticalOutput() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "EMA_MACD",
                "--fixtures",
                fixtureFile.absolutePath,
                "--instrument",
                "BTC/USD",
                "--output",
                "json",
            )

        // Act - Run identical invocation twice
        val run1 = cli.execute(args)
        val run2 = cli.execute(args)

        // Assert
        assertThat(run1.exitCode).isEqualTo(0)
        assertThat(run2.exitCode).isEqualTo(0)
        assertThat(run1.stdout).isNotEmpty()
        assertThat(run1.stdout).isEqualTo(run2.stdout)
        assertThat(run1.stderr).isEqualTo(run2.stderr)
    }

    @Test
    fun execute_withValidStrategyAndFixture_returnsExpectedJsonStructure() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "SMA_RSI",
                "--fixtures",
                fixtureFile.absolutePath,
                "--instrument",
                "BTC/USD",
                "--output",
                "json",
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)

        val json = JsonParser.parseString(result.stdout).asJsonObject
        assertThat(json.get("strategy").asString).isEqualTo("SMA_RSI")
        assertThat(json.get("instrument").asString).isEqualTo("BTC/USD")

        val period = json.getAsJsonObject("period")
        assertThat(period.get("start").asString).isEqualTo("2024-01-01T00:00:00Z")
        assertThat(period.get("end").asString).isEqualTo("2024-01-02T05:00:00Z")

        val metrics = json.getAsJsonObject("results")
        assertThat(metrics.has("total_return_pct")).isTrue()
        assertThat(metrics.has("sharpe_ratio")).isTrue()
        assertThat(metrics.has("max_drawdown_pct")).isTrue()
        assertThat(metrics.has("win_rate")).isTrue()
        assertThat(metrics.has("profit_factor")).isTrue()
        assertThat(metrics.has("total_trades")).isTrue()
        assertThat(metrics.has("avg_trade_duration")).isTrue()
        assertThat(metrics.has("strategy_score")).isTrue()

        assertThat(json.has("recommendation")).isTrue()
    }

    @Test
    fun execute_withTextOutput_printsFormattedText() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "SMA_RSI",
                "--fixtures",
                fixtureFile.absolutePath,
                "--output",
                "text",
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        assertThat(result.stdout).contains("TradeStream Backtest Summary")
        assertThat(result.stdout).contains("Strategy:           SMA_RSI")
        assertThat(result.stdout).contains("Instrument:         BTC/USD")
        assertThat(result.stdout).contains("Total Return:")
        assertThat(result.stdout).contains("Sharpe Ratio:")
        assertThat(result.stdout).contains("Recommendation:")
    }

    @Test
    fun execute_withCaseInsensitiveStrategyName_resolvesCorrectly() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "sma_rsi",
                "--fixtures",
                fixtureFile.absolutePath,
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(result.stdout).asJsonObject
        assertThat(json.get("strategy").asString).isEqualTo("SMA_RSI")
    }

    @Test
    fun execute_withLeadingSubcommand_stripsSubcommandAndRuns() {
        // Arrange - "tradestream backtest --strategy SMA_RSI"
        val args =
            arrayOf(
                "backtest",
                "--strategy",
                "SMA_RSI",
                "--fixtures",
                fixtureFile.absolutePath,
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(result.stdout).asJsonObject
        assertThat(json.get("strategy").asString).isEqualTo("SMA_RSI")
    }

    @Test
    fun execute_withUnsupportedStrategy_returnsErrorCodeAndListsStrategies() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "DEFINITELY_UNKNOWN_STRATEGY_XYZ",
                "--fixtures",
                fixtureFile.absolutePath,
            )

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
                "SMA_RSI",
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
    fun execute_withCustomFakeRunner_delegatesCorrectly() {
        // Arrange - Test with custom runner double to verify boundary isolation
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
                        .setWinRate(0.62)
                        .setProfitFactor(1.95)
                        .setVolatility(0.02)
                        .setNumberOfTrades(47)
                        .setAverageTradeDuration(15.5)
                        .setStrategyScore(0.88)
                        .build()
                }
            }

        val customCli = BacktestCli(fakeRunner)
        val args =
            arrayOf(
                "--strategy",
                "EMA_MACD",
                "--fixtures",
                fixtureFile.absolutePath,
                "--instrument",
                "ETH/USD",
            )

        // Act
        val result = customCli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        assertThat(requestReceived).isNotNull()
        assertThat(requestReceived!!.strategy.strategyName).isEqualTo("EMA_MACD")
        assertThat(requestReceived!!.candlesCount).isEqualTo(30)

        val json = JsonParser.parseString(result.stdout).asJsonObject
        assertThat(json.get("strategy").asString).isEqualTo("EMA_MACD")
        assertThat(json.get("instrument").asString).isEqualTo("ETH/USD")
        val metrics = json.getAsJsonObject("results")
        assertThat(metrics.get("total_trades").asInt).isEqualTo(47)
        assertThat(metrics.get("win_rate").asDouble).isEqualTo(0.62)
        assertThat(metrics.get("sharpe_ratio").asDouble).isEqualTo(1.85)
    }

    @Test
    fun execute_withDateRange_filtersCandlesCorrectly() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "SMA_RSI",
                "--fixtures",
                fixtureFile.absolutePath,
                "--start",
                "2024-01-01",
                "--end",
                "2024-01-01",
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(result.stdout).asJsonObject
        val period = json.getAsJsonObject("period")
        assertThat(period.get("start").asString).isEqualTo("2024-01-01T00:00:00Z")
        assertThat(period.get("end").asString).isEqualTo("2024-01-01T23:00:00Z")
        assertThat(result.backtestResult).isNotNull()
    }

    @Test
    fun execute_withMalformedDate_returnsExitCode2() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "SMA_RSI",
                "--fixtures",
                fixtureFile.absolutePath,
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
                "SMA_RSI",
                "--fixtures",
                fixtureFile.absolutePath,
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
    fun execute_withInitialCapital_setsCapitalInOutput() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "SMA_RSI",
                "--fixtures",
                fixtureFile.absolutePath,
                "--initial-capital",
                "50000.0",
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(result.stdout).asJsonObject
        val metrics = json.getAsJsonObject("results")
        assertThat(metrics.get("initial_capital").asDouble).isEqualTo(50000.0)
    }

    @Test
    fun execute_withInvalidInitialCapital_returnsExitCode2() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "SMA_RSI",
                "--fixtures",
                fixtureFile.absolutePath,
                "--initial-capital",
                "0.0",
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(2)
        assertThat(result.stderr).contains("must be greater than 0")
    }

    @Test
    fun execute_withValidParamsOverride_updatesParametersAndPopulatesResult() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "SMA_RSI",
                "--fixtures",
                fixtureFile.absolutePath,
                "--params",
                "{\"movingAveragePeriod\": 10, \"rsiPeriod\": 7}",
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(0)
        assertThat(result.backtestResult).isNotNull()
    }

    @Test
    fun execute_withInvalidParamsJson_returnsExitCode2() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "SMA_RSI",
                "--fixtures",
                fixtureFile.absolutePath,
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
