package com.verlumen.tradestream.backtesting

import com.google.inject.Inject
import kotlin.math.sqrt

/**
 * Implementation of [StrategyComparator] that runs backtests for each strategy,
 * ranks results by a user-selected metric, and computes pairwise return correlations.
 */
class StrategyComparatorImpl
    @Inject
    constructor(
        private val backtestRunner: BacktestRunner,
    ) : StrategyComparator {
    override fun compare(request: StrategyComparisonRequest): StrategyComparisonResult {
        require(request.strategiesList.size >= 2) {
            "At least 2 strategies are required for comparison"
        }
        require(request.candlesList.isNotEmpty()) { "Candle data cannot be empty" }

        val rankingMetric =
            if (request.rankingMetric == RankingMetric.RANKING_METRIC_UNSPECIFIED) {
                RankingMetric.STRATEGY_SCORE
            } else {
                request.rankingMetric
            }

        // Run backtests for each strategy
        val strategyResults =
            request.strategiesList.map { strategy ->
                val backtestRequest =
                    BacktestRequest
                        .newBuilder()
                        .addAllCandles(request.candlesList)
                        .setStrategy(strategy)
                        .build()
                strategy to backtestRunner.runBacktest(backtestRequest)
            }

        // Sort by ranking metric (descending for most metrics, ascending for drawdown)
        val sorted =
            strategyResults.sortedWith(
                if (rankingMetric == RankingMetric.MAX_DRAWDOWN) {
                    compareBy { extractMetric(it.second, rankingMetric) }
                } else {
                    compareByDescending { extractMetric(it.second, rankingMetric) }
                },
            )

        // Build ranked entries
        val entries =
            sorted.mapIndexed { index, (strategy, result) ->
                StrategyComparisonEntry
                    .newBuilder()
                    .setStrategy(strategy)
                    .setResult(result)
                    .setRank(index + 1)
                    .build()
            }

        // Compute pairwise return correlations
        val correlations = computeCorrelations(strategyResults)

        return StrategyComparisonResult
            .newBuilder()
            .addAllEntries(entries)
            .setRankingMetric(rankingMetric)
            .addAllCorrelations(correlations)
            .setStrategyCount(request.strategiesList.size)
            .build()
    }

    companion object {
        fun extractMetric(
            result: BacktestResult,
            metric: RankingMetric,
        ): Double =
            when (metric) {
                RankingMetric.STRATEGY_SCORE -> result.strategyScore
                RankingMetric.SHARPE_RATIO -> result.sharpeRatio
                RankingMetric.CUMULATIVE_RETURN -> result.cumulativeReturn
                RankingMetric.MAX_DRAWDOWN -> result.maxDrawdown
                RankingMetric.WIN_RATE -> result.winRate
                RankingMetric.PROFIT_FACTOR -> result.profitFactor
                RankingMetric.SORTINO_RATIO -> result.sortinoRatio
                else -> result.strategyScore
            }

        fun pearsonCorrelation(
            xs: List<Double>,
            ys: List<Double>,
        ): Double {
            require(xs.size == ys.size) { "Series must be the same length" }
            val n = xs.size
            if (n < 2) return 0.0

            val meanX = xs.average()
            val meanY = ys.average()

            var sumXY = 0.0
            var sumX2 = 0.0
            var sumY2 = 0.0
            for (i in 0 until n) {
                val dx = xs[i] - meanX
                val dy = ys[i] - meanY
                sumXY += dx * dy
                sumX2 += dx * dx
                sumY2 += dy * dy
            }

            val denominator = sqrt(sumX2) * sqrt(sumY2)
            return if (denominator == 0.0) 0.0 else sumXY / denominator
        }
    }

    private fun computeCorrelations(
        strategyResults: List<Pair<com.verlumen.tradestream.strategies.Strategy, BacktestResult>>,
    ): List<ReturnCorrelation> {
        // Use cumulative return and sharpe as a simple proxy for return profile.
        // For a more complete analysis, per-bar returns would be needed, but the
        // BacktestResult only provides aggregated metrics. We correlate the metric
        // vectors across strategies pairwise.
        val correlations = mutableListOf<ReturnCorrelation>()
        val metricVectors =
            strategyResults.map { (strategy, result) ->
                strategy.strategyName to
                    listOf(
                        result.cumulativeReturn,
                        result.annualizedReturn,
                        result.sharpeRatio,
                        result.sortinoRatio,
                        result.winRate,
                        result.profitFactor,
                        result.maxDrawdown,
                        result.volatility,
                    )
            }

        for (i in metricVectors.indices) {
            for (j in i + 1 until metricVectors.size) {
                val (nameA, metricsA) = metricVectors[i]
                val (nameB, metricsB) = metricVectors[j]
                val correlation = pearsonCorrelation(metricsA, metricsB)
                correlations.add(
                    ReturnCorrelation
                        .newBuilder()
                        .setStrategyA(nameA)
                        .setStrategyB(nameB)
                        .setCorrelation(correlation)
                        .build(),
                )
            }
        }

        return correlations
    }
}
