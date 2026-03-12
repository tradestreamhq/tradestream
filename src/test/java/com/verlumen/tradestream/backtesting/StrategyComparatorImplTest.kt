package com.verlumen.tradestream.backtesting

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.Any
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategySpecs
import java.time.ZonedDateTime
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class StrategyComparatorImplTest {
    private lateinit var comparator: StrategyComparatorImpl
    private lateinit var candles: List<Candle>
    private val startTime: ZonedDateTime = ZonedDateTime.now()

    @Before
    fun setUp() {
        val backtestRunner = FakeBacktestRunner()
        comparator = StrategyComparatorImpl(backtestRunner)
        candles = createTestCandles()
    }

    @Test(expected = IllegalArgumentException::class)
    fun compare_withFewerThanTwoStrategies_throwsException() {
        val request =
            StrategyComparisonRequest
                .newBuilder()
                .addAllCandles(candles)
                .addStrategies(createStrategy("SMA_RSI"))
                .build()
        comparator.compare(request)
    }

    @Test(expected = IllegalArgumentException::class)
    fun compare_withEmptyCandles_throwsException() {
        val request =
            StrategyComparisonRequest
                .newBuilder()
                .addStrategies(createStrategy("SMA_RSI"))
                .addStrategies(createStrategy("EMA_MACD"))
                .build()
        comparator.compare(request)
    }

    @Test
    fun compare_withTwoStrategies_returnsRankedResults() {
        val request =
            StrategyComparisonRequest
                .newBuilder()
                .addAllCandles(candles)
                .addStrategies(createStrategy("SMA_RSI"))
                .addStrategies(createStrategy("EMA_MACD"))
                .setRankingMetric(RankingMetric.STRATEGY_SCORE)
                .build()

        val result = comparator.compare(request)

        assertThat(result.strategyCount).isEqualTo(2)
        assertThat(result.entriesList).hasSize(2)
        assertThat(result.entriesList[0].rank).isEqualTo(1)
        assertThat(result.entriesList[1].rank).isEqualTo(2)
        assertThat(result.rankingMetric).isEqualTo(RankingMetric.STRATEGY_SCORE)
    }

    @Test
    fun compare_ranksDescendingByDefault() {
        val request =
            StrategyComparisonRequest
                .newBuilder()
                .addAllCandles(candles)
                .addStrategies(createStrategy("SMA_RSI"))
                .addStrategies(createStrategy("EMA_MACD"))
                .setRankingMetric(RankingMetric.SHARPE_RATIO)
                .build()

        val result = comparator.compare(request)

        val firstSharpe = result.entriesList[0].result.sharpeRatio
        val secondSharpe = result.entriesList[1].result.sharpeRatio
        assertThat(firstSharpe).isAtLeast(secondSharpe)
    }

    @Test
    fun compare_maxDrawdownRanksAscending() {
        val request =
            StrategyComparisonRequest
                .newBuilder()
                .addAllCandles(candles)
                .addStrategies(createStrategy("SMA_RSI"))
                .addStrategies(createStrategy("EMA_MACD"))
                .setRankingMetric(RankingMetric.MAX_DRAWDOWN)
                .build()

        val result = comparator.compare(request)

        val firstDrawdown = result.entriesList[0].result.maxDrawdown
        val secondDrawdown = result.entriesList[1].result.maxDrawdown
        assertThat(firstDrawdown).isAtMost(secondDrawdown)
    }

    @Test
    fun compare_defaultsToStrategyScoreWhenUnspecified() {
        val request =
            StrategyComparisonRequest
                .newBuilder()
                .addAllCandles(candles)
                .addStrategies(createStrategy("SMA_RSI"))
                .addStrategies(createStrategy("EMA_MACD"))
                .build()

        val result = comparator.compare(request)

        assertThat(result.rankingMetric).isEqualTo(RankingMetric.STRATEGY_SCORE)
    }

    @Test
    fun compare_computesCorrelations() {
        val request =
            StrategyComparisonRequest
                .newBuilder()
                .addAllCandles(candles)
                .addStrategies(createStrategy("SMA_RSI"))
                .addStrategies(createStrategy("EMA_MACD"))
                .build()

        val result = comparator.compare(request)

        assertThat(result.correlationsList).hasSize(1)
        val correlation = result.correlationsList[0]
        assertThat(correlation.strategyA).isNotEmpty()
        assertThat(correlation.strategyB).isNotEmpty()
        assertThat(correlation.correlation).isAtLeast(-1.0)
        assertThat(correlation.correlation).isAtMost(1.0)
    }

    @Test
    fun compare_withThreeStrategies_producesThreeCorrelations() {
        val request =
            StrategyComparisonRequest
                .newBuilder()
                .addAllCandles(candles)
                .addStrategies(createStrategy("SMA_RSI"))
                .addStrategies(createStrategy("EMA_MACD"))
                .addStrategies(createStrategy("MACD_CROSSOVER"))
                .build()

        val result = comparator.compare(request)

        // 3 strategies -> C(3,2) = 3 pairwise correlations
        assertThat(result.correlationsList).hasSize(3)
        assertThat(result.strategyCount).isEqualTo(3)
        assertThat(result.entriesList).hasSize(3)
    }

    @Test
    fun compare_entriesContainStrategyAndResult() {
        val request =
            StrategyComparisonRequest
                .newBuilder()
                .addAllCandles(candles)
                .addStrategies(createStrategy("SMA_RSI"))
                .addStrategies(createStrategy("EMA_MACD"))
                .build()

        val result = comparator.compare(request)

        for (entry in result.entriesList) {
            assertThat(entry.strategy.strategyName).isNotEmpty()
            assertThat(entry.hasResult()).isTrue()
            assertThat(entry.result.winRate).isAtLeast(0.0)
            assertThat(entry.result.winRate).isAtMost(1.0)
        }
    }

    @Test
    fun pearsonCorrelation_perfectPositive_returnsOne() {
        val xs = listOf(1.0, 2.0, 3.0, 4.0, 5.0)
        val ys = listOf(2.0, 4.0, 6.0, 8.0, 10.0)
        val correlation = StrategyComparatorImpl.pearsonCorrelation(xs, ys)
        assertThat(correlation).isWithin(1e-9).of(1.0)
    }

    @Test
    fun pearsonCorrelation_perfectNegative_returnsNegativeOne() {
        val xs = listOf(1.0, 2.0, 3.0, 4.0, 5.0)
        val ys = listOf(10.0, 8.0, 6.0, 4.0, 2.0)
        val correlation = StrategyComparatorImpl.pearsonCorrelation(xs, ys)
        assertThat(correlation).isWithin(1e-9).of(-1.0)
    }

    @Test
    fun pearsonCorrelation_constantSeries_returnsZero() {
        val xs = listOf(1.0, 1.0, 1.0, 1.0)
        val ys = listOf(2.0, 4.0, 6.0, 8.0)
        val correlation = StrategyComparatorImpl.pearsonCorrelation(xs, ys)
        assertThat(correlation).isWithin(1e-9).of(0.0)
    }

    @Test
    fun pearsonCorrelation_singleElement_returnsZero() {
        val xs = listOf(5.0)
        val ys = listOf(10.0)
        val correlation = StrategyComparatorImpl.pearsonCorrelation(xs, ys)
        assertThat(correlation).isWithin(1e-9).of(0.0)
    }

    @Test
    fun extractMetric_allMetricTypes() {
        val result =
            BacktestResult
                .newBuilder()
                .setStrategyScore(0.8)
                .setSharpeRatio(1.5)
                .setCumulativeReturn(0.25)
                .setMaxDrawdown(0.1)
                .setWinRate(0.6)
                .setProfitFactor(1.8)
                .setSortinoRatio(2.0)
                .build()

        assertThat(StrategyComparatorImpl.extractMetric(result, RankingMetric.STRATEGY_SCORE))
            .isEqualTo(0.8)
        assertThat(StrategyComparatorImpl.extractMetric(result, RankingMetric.SHARPE_RATIO))
            .isEqualTo(1.5)
        assertThat(StrategyComparatorImpl.extractMetric(result, RankingMetric.CUMULATIVE_RETURN))
            .isEqualTo(0.25)
        assertThat(StrategyComparatorImpl.extractMetric(result, RankingMetric.MAX_DRAWDOWN))
            .isEqualTo(0.1)
        assertThat(StrategyComparatorImpl.extractMetric(result, RankingMetric.WIN_RATE))
            .isEqualTo(0.6)
        assertThat(StrategyComparatorImpl.extractMetric(result, RankingMetric.PROFIT_FACTOR))
            .isEqualTo(1.8)
        assertThat(StrategyComparatorImpl.extractMetric(result, RankingMetric.SORTINO_RATIO))
            .isEqualTo(2.0)
    }

    private fun createStrategy(name: String): Strategy {
        val spec = StrategySpecs.getSpec(name)
        return Strategy
            .newBuilder()
            .setStrategyName(name)
            .setParameters(Any.pack(spec.strategyFactory.defaultParameters))
            .build()
    }

    private fun createTestCandles(): List<Candle> {
        val result = mutableListOf<Candle>()
        var basePrice = 100.0
        // Create enough bars for strategies to generate signals
        for (i in 0 until 35) {
            basePrice += if (i < 10) 0.5 else if (i < 20) -3.0 else 2.0
            basePrice = maxOf(basePrice, 50.0)
            result.add(createCandle(startTime.plusMinutes(i.toLong()), basePrice))
        }
        return result
    }

    private fun createCandle(
        time: ZonedDateTime,
        price: Double,
    ): Candle =
        Candle
            .newBuilder()
            .setTimestamp(Timestamps.fromMillis(time.toInstant().toEpochMilli()))
            .setOpen(price)
            .setHigh(price * 1.01)
            .setLow(price * 0.99)
            .setClose(price)
            .setVolume(100)
            .setCurrencyPair("BTC/USD")
            .build()

    /** Fake BacktestRunner that returns deterministic results based on strategy name hash. */
    private class FakeBacktestRunner : BacktestRunner {
        override fun runBacktest(request: BacktestRequest): BacktestResult {
            val hash = request.strategy.strategyName.hashCode()
            val seed = (hash.toLong() and 0xFFFFFFFFL).toDouble() / Int.MAX_VALUE.toDouble()
            return BacktestResult
                .newBuilder()
                .setCumulativeReturn(seed * 0.5)
                .setAnnualizedReturn(seed * 0.3)
                .setSharpeRatio(seed * 2.0)
                .setSortinoRatio(seed * 2.5)
                .setMaxDrawdown(seed * 0.4)
                .setVolatility(seed * 0.2)
                .setWinRate(0.3 + seed * 0.4)
                .setProfitFactor(0.5 + seed * 1.5)
                .setNumberOfTrades(10 + (seed * 20).toInt())
                .setAverageTradeDuration(5.0 + seed * 10)
                .setStrategyScore(0.2 + seed * 0.6)
                .build()
        }
    }
}
