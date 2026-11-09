package com.verlumen.tradestream.backtesting.cli

import com.google.common.truth.Truth.assertThat
import com.google.gson.JsonParser
import com.verlumen.tradestream.backtesting.BacktestRequest
import com.verlumen.tradestream.backtesting.BacktestResult
import com.verlumen.tradestream.backtesting.BacktestRunner
import com.verlumen.tradestream.strategies.emamacd.EmaMacdStrategyFactory
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import java.time.Instant

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
        val file = cli.resolveFixtureFile(BacktestCli.DEFAULT_FIXTURE_PATH)
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

    private fun addRamp(prices: MutableList<Double>, start: Double, end: Double, steps: Int) {
        val step = (end - start) / steps
        for (i in 0 until steps) {
            prices.add(kotlin.math.round((start + i * step) * 100.0) / 100.0)
        }
    }

    /**
     * Independently computes EMA(shortPeriod)/EMA(longPeriod) MACD crossover trades matching ta4j's
     * org.ta4j:ta4j-core:0.22.0 convention:
     * - EMA(shortPeriod) is seeded at bar shortPeriod with close[shortPeriod].
     * - EMA(longPeriod) is seeded at bar longPeriod with close[longPeriod].
     * - MACD line = EMA(shortPeriod) - EMA(longPeriod), defined from bar longPeriod onward.
     * - Signal line = signalPeriod-period EMA of MACD, seeded at bar longPeriod with macd[longPeriod] (matching
     *   EmaMacdStrategyFactory with unstableBars = longPeriod).
     * - Entry on CrossedUp (macd crosses above signal) and exit on CrossedDown (macd crosses below signal),
     *   walking backward across intermediate equality plateaus (macd == signal) to find the prior unequal bar.
     */
    private fun computeIndependentEmaMacdTrades(
        closes: List<Double>,
        shortPeriod: Int = 12,
        longPeriod: Int = 26,
        signalPeriod: Int = 9,
    ): List<IndependentTrade> {
        val emaShort = computeIndependentEma(closes, startIndex = shortPeriod, period = shortPeriod)
        val emaLong = computeIndependentEma(closes, startIndex = longPeriod, period = longPeriod)
        val macd = ArrayList<Double?>(closes.size)
        for (i in closes.indices) {
            val eS = emaShort[i]
            val eL = emaLong[i]
            if (eS != null && eL != null) {
                macd.add(eS - eL)
            } else {
                macd.add(null)
            }
        }
        val signalValues = macd.drop(longPeriod).filterNotNull()
        val signalEma = computeIndependentEma(signalValues, startIndex = 0, period = signalPeriod)
        val signal = ArrayList<Double?>(closes.size)
        for (i in 0 until longPeriod) {
            signal.add(null)
        }
        signal.addAll(signalEma)

        val trades = mutableListOf<IndependentTrade>()
        var entryBar: Int? = null

        for (i in (longPeriod + 1) until closes.size) {
            val currM = macd[i] ?: continue
            val currS = signal[i] ?: continue

            var crossedOver = false
            if (currM > currS) {
                for (prevIdx in (i - 1) downTo 0) {
                    val pM = macd[prevIdx] ?: break
                    val pS = signal[prevIdx] ?: break
                    if (pM < pS) {
                        crossedOver = true
                        break
                    } else if (pM > pS) {
                        break
                    }
                }
            }

            var crossedUnder = false
            if (currM < currS) {
                for (prevIdx in (i - 1) downTo 0) {
                    val pM = macd[prevIdx] ?: break
                    val pS = signal[prevIdx] ?: break
                    if (pM > pS) {
                        crossedUnder = true
                        break
                    } else if (pM < pS) {
                        break
                    }
                }
            }

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
        assertThat(results.get("win_rate").isJsonNull).isTrue()
        assertThat(results.get("profit_factor").isJsonNull).isTrue()
        assertThat(results.get("avg_trade_duration_bars").isJsonNull).isTrue()
    }

    @Test
    fun execute_isDeterministic_sameInputOnCheckedInFixtureProducesIdenticalOutput() {
        // Arrange - Create two fresh separate CLI instances
        val cli1 = BacktestCli.createDefault()
        val cli2 = BacktestCli.createDefault()
        val args = arrayOf("--strategy", "EMA_MACD")

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

        val args = arrayOf("--strategy", "EMA_MACD")

        // Act - Run CLI
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
        assertThat(results.get("avg_trade_duration_bars").asDouble).isEqualTo(expectedDurationBars)

        // With 1 winning trade and 0 losses, gross_loss == 0 so profit_factor is null (undefined)
        assertThat(results.get("profit_factor").isJsonNull).isTrue()

        // Verify excluded metrics from Issue #1461
        assertThat(results.has("sharpe_ratio")).isFalse()
        assertThat(results.has("sortino_ratio")).isFalse()
        assertThat(results.has("strategy_score")).isFalse()
        assertThat(results.has("annualized_return")).isFalse()
        assertThat(results.has("max_drawdown")).isFalse()
        assertThat(results.has("volatility")).isFalse()

        assertThat(json.has("recommendation")).isFalse()
        assertThat(results.has("total_return_pct")).isFalse()
    }

    @Suppress("DEPRECATION")
    @Test
    fun execute_withMultiCrossingFixtureAndEmaMacd_computesTrueProfitFactorAndDiscriminatesParameters() {
        // 1. Assert default parameters directly from EmaMacdStrategyFactory
        val defaultParams = EmaMacdStrategyFactory().defaultParameters
        assertThat(defaultParams.shortEmaPeriod).isEqualTo(12)
        assertThat(defaultParams.longEmaPeriod).isEqualTo(26)
        assertThat(defaultParams.signalPeriod).isEqualTo(9)

        // 2. Generate deterministic synthetic hourly price trajectory with 3 closed trades (2 wins, 1 loss)
        val prices = mutableListOf<Double>()
        for (i in 0 until 27) prices.add(100.0)
        addRamp(prices, 100.0, 95.0, 8)
        for (i in 0 until 5) prices.add(95.0)
        addRamp(prices, 95.0, 125.0, 17)
        addRamp(prices, 125.0, 118.0, 12)
        for (i in 0 until 10) prices.add(118.0)
        addRamp(prices, 118.0, 126.0, 8)
        addRamp(prices, 126.0, 100.0, 15)
        for (i in 0 until 10) prices.add(100.0)
        addRamp(prices, 100.0, 145.0, 15)
        addRamp(prices, 145.0, 135.0, 15)
        for (i in 0 until 15) prices.add(135.0)

        // 3. Verify independent oracle produces 3 closed trades (2 wins, 1 loss) for default (12, 26, 9)
        val defaultTrades = computeIndependentEmaMacdTrades(prices, 12, 26, 9)
        assertThat(defaultTrades).hasSize(3)
        val wins = defaultTrades.filter { it.grossPnl > 0.0 }
        val losses = defaultTrades.filter { it.grossPnl < 0.0 }
        assertThat(wins).hasSize(2)
        assertThat(losses).hasSize(1)

        val grossProfit = wins.sumOf { it.grossPnl }
        val grossLoss = kotlin.math.abs(losses.sumOf { it.grossPnl })
        val expectedProfitFactor = kotlin.math.round((grossProfit / grossLoss) * 10000.0) / 10000.0
        val avgWin = grossProfit / wins.size
        val avgLoss = grossLoss / losses.size
        val oldTa4jRatioOfAverages = kotlin.math.round((avgWin / avgLoss) * 10000.0) / 10000.0
        assertThat(expectedProfitFactor).isEqualTo(28.4727)
        assertThat(oldTa4jRatioOfAverages).isEqualTo(14.2364)
        assertThat(expectedProfitFactor).isNotEqualTo(oldTa4jRatioOfAverages)

        // 4. Prove that perturbing any single parameter by ±1 discriminates and changes execution
        assertThat(computeIndependentEmaMacdTrades(prices, 11, 26, 9)).isNotEqualTo(defaultTrades)
        assertThat(computeIndependentEmaMacdTrades(prices, 13, 26, 9)).isNotEqualTo(defaultTrades)
        assertThat(computeIndependentEmaMacdTrades(prices, 12, 25, 9)).isNotEqualTo(defaultTrades)
        assertThat(computeIndependentEmaMacdTrades(prices, 12, 27, 9)).isNotEqualTo(defaultTrades)
        assertThat(computeIndependentEmaMacdTrades(prices, 12, 26, 8)).isNotEqualTo(defaultTrades)
        assertThat(computeIndependentEmaMacdTrades(prices, 12, 26, 10)).isNotEqualTo(defaultTrades)

        // 5. Write synthetic CSV fixture
        val csvFile = tempFolder.newFile("multi_crossing_hourly.csv")
        val baseTime = Instant.parse("2024-01-01T00:00:00Z")
        csvFile.bufferedWriter().use { writer ->
            writer.write("timestamp,open,high,low,close,volume\n")
            prices.forEachIndexed { idx, close ->
                val timeStr = baseTime.plusSeconds(idx * 3600L).toString()
                val high = close * 1.01
                val low = close * 0.99
                writer.write("$timeStr,$close,$high,$low,$close,100.0\n")
            }
        }

        // 6. Run BacktestCli on synthetic CSV
        val result = cli.execute(arrayOf("--strategy", "EMA_MACD", "--fixtures", csvFile.absolutePath))
        assertThat(result.exitCode).isEqualTo(0)

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

        val initialClose = prices.first()
        val expectedPositionUnits = 10000.0 / initialClose
        val grossPnlPerUnit = kotlin.math.round(defaultTrades.sumOf { it.grossPnl } * 100.0) / 100.0
        val expectedGrossPnl = kotlin.math.round(expectedPositionUnits * grossPnlPerUnit * 100.0) / 100.0
        val expectedFinalCapital = kotlin.math.round((10000.0 + expectedGrossPnl) * 100.0) / 100.0

        assertThat(metrics.get("initial_capital").asDouble).isEqualTo(10000.0)
        assertThat(metrics.get("position_units").asDouble).isEqualTo(expectedPositionUnits)
        assertThat(metrics.get("gross_pnl_per_unit").asDouble).isEqualTo(60.44)
        assertThat(metrics.get("gross_pnl").asDouble).isEqualTo(6044.0)
        assertThat(metrics.get("final_capital").asDouble).isEqualTo(expectedFinalCapital)
        assertThat(metrics.get("total_trades").asInt).isEqualTo(3)
        assertThat(metrics.get("win_rate").asDouble).isEqualTo(0.6667)
        assertThat(metrics.get("profit_factor").asDouble).isEqualTo(expectedProfitFactor)
        assertThat(metrics.get("profit_factor").asDouble).isNotEqualTo(oldTa4jRatioOfAverages)
        assertThat(metrics.get("avg_trade_duration_bars").asDouble).isEqualTo(16.7)
    }

    @Test
    fun execute_withDifferentInitialCapital_changesPositionSizeAndExecutionDerivedResults() {
        // Run 1: default 10000.0 (0.237248 BTC at initial close 42150.0)
        val res10k = cli.execute(arrayOf("--strategy", "EMA_MACD", "--initial-capital", "10000"))
        assertThat(res10k.exitCode).isEqualTo(0)
        val json10k = JsonParser.parseString(res10k.stdout).asJsonObject.getAsJsonObject("results")
        assertThat(json10k.get("initial_capital").asDouble).isEqualTo(10000.0)
        assertThat(json10k.get("position_units").asDouble).isEqualTo(0.237248)
        assertThat(json10k.get("gross_pnl_per_unit").asDouble).isEqualTo(100.0)
        assertThat(json10k.get("gross_pnl").asDouble).isEqualTo(23.72)
        assertThat(json10k.get("final_capital").asDouble).isEqualTo(10023.72)

        // Run 2: 42150.0 (exactly 1.0 BTC at initial close 42150.0)
        val res42k = cli.execute(arrayOf("--strategy", "EMA_MACD", "--initial-capital", "42150"))
        assertThat(res42k.exitCode).isEqualTo(0)
        val json42k = JsonParser.parseString(res42k.stdout).asJsonObject.getAsJsonObject("results")
        assertThat(json42k.get("initial_capital").asDouble).isEqualTo(42150.0)
        assertThat(json42k.get("position_units").asDouble).isEqualTo(1.0)
        assertThat(json42k.get("gross_pnl_per_unit").asDouble).isEqualTo(100.0)
        assertThat(json42k.get("gross_pnl").asDouble).isEqualTo(100.0)
        assertThat(json42k.get("final_capital").asDouble).isEqualTo(42250.0)

        // Run 3: -c 21075 (exactly 0.5 BTC at initial close 42150.0)
        val res21k = cli.execute(arrayOf("--strategy", "EMA_MACD", "-c", "21075"))
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
        // Arrange - Test with custom runner double pinning all 8 well-defined fields
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
        val args = arrayOf("--strategy", "EMA_MACD")

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
    fun execute_withNonFiniteValues_serializesAsJsonNull() {
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

        val jsonResult = customCli.execute(arrayOf("--strategy", "EMA_MACD"))
        assertThat(jsonResult.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(jsonResult.stdout).asJsonObject
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
        assertThat(results.get("gross_pnl_per_unit").isJsonNull).isTrue()
        assertThat(results.get("gross_pnl").isJsonNull).isTrue()
        assertThat(results.get("final_capital").isJsonNull).isTrue()
        assertThat(results.get("win_rate").isJsonNull).isTrue()
        assertThat(results.get("profit_factor").isJsonNull).isTrue()
        assertThat(results.get("avg_trade_duration_bars").isJsonNull).isTrue()
        assertThat(results.get("total_trades").asInt).isEqualTo(0)
    }

    @Test
    fun execute_withOverflowingInitialCapital_serializesOverflowedMetricsAsJsonNull() {
        val result = cli.execute(arrayOf("--strategy", "EMA_MACD", "--initial-capital", "1e308"))
        assertThat(result.exitCode).isEqualTo(0)
        val json = JsonParser.parseString(result.stdout).asJsonObject
        val results = json.getAsJsonObject("results")
        assertThat(results.get("initial_capital").isJsonNull).isTrue()
        assertThat(results.get("final_capital").isJsonNull).isTrue()
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

        val normalizedStdout = result.stdout.replace(Regex("\\s+"), " ")
        assertThat(normalizedStdout).contains("fixture-only, long-only, 1-unit runner trades")
        assertThat(normalizedStdout).contains("initial_capital / first filtered close")
        assertThat(normalizedStdout).contains("closed-trade gross P&L only")
        assertThat(normalizedStdout).contains("no open-position valuation")
        assertThat(normalizedStdout).contains("no compounding")
    }

    @Test
    fun execute_withDateRange_filtersCandlesCorrectly() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "EMA_MACD",
                "--start",
                "2024-01-01T00:00:00Z",
                "--end",
                "2024-01-02T23:00:00Z",
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
        assertThat(result.stderr).contains("Malformed ISO-8601 timestamp")
    }

    @Test
    fun execute_withStartAfterEnd_returnsExitCode2() {
        // Arrange
        val args =
            arrayOf(
                "--strategy",
                "EMA_MACD",
                "--start",
                "2024-01-02T00:00:00Z",
                "--end",
                "2024-01-01T00:00:00Z",
            )

        // Act
        val result = cli.execute(args)

        // Assert
        assertThat(result.exitCode).isEqualTo(2)
        assertThat(result.stderr).contains("cannot be after end date")
    }
}
