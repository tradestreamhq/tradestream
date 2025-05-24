package com.verlumen.tradestream.backtesting

import com.google.inject.Inject
import com.google.protobuf.InvalidProtocolBufferException
import com.verlumen.tradestream.strategies.StrategyManager
import com.verlumen.tradestream.ta4j.BarSeriesFactory
import org.ta4j.core.AnalysisCriterion
import org.ta4j.core.BarSeries
import org.ta4j.core.BaseTradingRecord
import org.ta4j.core.Strategy
import org.ta4j.core.TradingRecord
import org.ta4j.core.criteria.pnl.ProfitLossCriterion
import org.ta4j.core.criteria.pnl.ProfitLossRatioCriterion
import org.ta4j.core.criteria.pnl.ReturnCriterion
import kotlin.math.max
import kotlin.math.pow
import kotlin.math.sqrt

/**
 * Implementation of BacktestRunner that evaluates trading strategies using Ta4j.
 */
internal class BacktestRunnerImpl
    @Inject
    constructor(
        private val barSeriesFactory: BarSeriesFactory,
        private val strategyManager: StrategyManager,
    ) : BacktestRunner {
        @Throws(InvalidProtocolBufferException::class)
        override fun runBacktest(request: BacktestRequest): BacktestResult {
            require(request.candlesList.isNotEmpty()) { "Bar series cannot be empty" }

            val series = barSeriesFactory.createBarSeries(request.candlesList)
            val strategy =
                strategyManager.createStrategy(
                    series,
                    request.strategy.type,
                    request.strategy.parameters,
                )

            // Run the strategy
            val tradingRecord = runStrategy(series, strategy)

            // Calculate basic metrics
            val cumulativeReturn = calculateMetric(series, tradingRecord, ProfitLossCriterion())
            val profitFactor = calculateMetric(series, tradingRecord, ProfitLossRatioCriterion())
            val annualizedReturn = calculateAnnualizedReturn(series, tradingRecord)

            // Calculate risk metrics
            val volatility = calculateVolatility(series)
            val maxDrawdown = calculateMaxDrawdown(series)

            // Trade statistics
            val numberOfTrades = tradingRecord.positions.size
            val winRate = calculateWinRate(tradingRecord)
            val averageTradeDuration = calculateAverageTradeDuration(tradingRecord)

            // Risk-adjusted returns
            val sharpeRatio = calculateSharpeRatio(cumulativeReturn, volatility)
            val sortinoRatio = calculateSortinoRatio(series, tradingRecord)

            // Alpha/Beta (simplified calculation)
            val alpha = 0.0 // TODO: Implement when benchmark data is available
            val beta = 1.0 // TODO: Implement when benchmark data is available

            val score = calculateScore(sharpeRatio, maxDrawdown, winRate, annualizedReturn, profitFactor)

            return BacktestResult.newBuilder()
                .setCumulativeReturn(cumulativeReturn)
                .setAnnualizedReturn(annualizedReturn)
                .setSharpeRatio(sharpeRatio)
                .setSortinoRatio(sortinoRatio)
                .setMaxDrawdown(maxDrawdown)
                .setVolatility(volatility)
                .setWinRate(winRate)
                .setProfitFactor(profitFactor)
                .setNumberOfTrades(numberOfTrades)
                .setAverageTradeDuration(averageTradeDuration)
                .setAlpha(alpha)
                .setBeta(beta)
                .setStrategyScore(score)
                .build()
        }

        private fun runStrategy(
            series: BarSeries,
            strategy: Strategy,
        ): TradingRecord {
            val tradingRecord = BaseTradingRecord()

            // Skip unstable period at the start
            for (i in strategy.unstableBars until series.barCount) {
                // Check if we should enter long position
                if (strategy.shouldEnter(i)) {
                    // Enter with a position size of 1 unit
                    tradingRecord.enter(i, series.getBar(i).closePrice, series.numOf(1))
                }
                // Check if we should exit an open position
                else if (strategy.shouldExit(i) && tradingRecord.currentPosition.isOpened) {
                    tradingRecord.exit(i, series.getBar(i).closePrice, series.numOf(1))
                }
            }

            return tradingRecord
        }

        private fun calculateMetric(
            series: BarSeries,
            record: TradingRecord,
            criterion: AnalysisCriterion,
        ): Double = criterion.calculate(series, record).doubleValue()

        private fun calculateVolatility(series: BarSeries): Double {
            if (series.barCount < 2) {
                return 0.0
            }

            val returns =
                (1 until series.barCount).map { i ->
                    val previousClose = series.getBar(i - 1).closePrice
                    val currentClose = series.getBar(i).closePrice
                    currentClose.minus(previousClose)
                        .dividedBy(previousClose)
                        .doubleValue()
                }

            // Calculate standard deviation
            val mean = returns.average()
            val variance = returns.map { (it - mean).pow(2) }.average()

            return sqrt(variance)
        }

        private fun calculateMaxDrawdown(series: BarSeries): Double {
            if (series.barCount == 0) {
                return 0.0
            }

            var maxDrawdown = 0.0
            var peak = series.getBar(0).closePrice.doubleValue()

            (1 until series.barCount).forEach { i ->
                val price = series.getBar(i).closePrice.doubleValue()

                if (price > peak) {
                    peak = price
                }

                val drawdown = (peak - price) / peak
                maxDrawdown = max(maxDrawdown, drawdown)
            }

            return maxDrawdown
        }

        private fun calculateWinRate(record: TradingRecord): Double {
            if (record.positions.isEmpty()) {
                return 0.0
            }

            val winningTrades =
                record.positions
                    .count { it.isClosed && it.profit.isPositive }

            return winningTrades.toDouble() / record.positions.size
        }

        private fun calculateAverageTradeDuration(record: TradingRecord): Double {
            val closedPositions = record.positions.filter { it.isClosed }
            if (closedPositions.isEmpty()) {
                return 0.0
            }

            val totalDuration =
                closedPositions.sumOf {
                    it.exit.index - it.entry.index
                }

            return totalDuration.toDouble() / closedPositions.size
        }

        private fun calculateAnnualizedReturn(
            series: BarSeries,
            record: TradingRecord,
        ): Double {
            val totalReturn = calculateMetric(series, record, ReturnCriterion())
            val barsPerYear = 252 * 1440 // Assuming 1-minute bars and 252 trading days
            val years = series.barCount.toDouble() / barsPerYear

            // Use compound annual growth rate formula
            return (1 + totalReturn).pow(1 / years) - 1
        }

        private fun calculateSharpeRatio(
            returns: Double,
            volatility: Double,
        ): Double {
            val riskFreeRate = 0.02 // Assume 2% risk-free rate
            return if (volatility == 0.0) 0.0 else (returns - riskFreeRate) / volatility
        }

        private fun calculateSortinoRatio(
            series: BarSeries,
            record: TradingRecord,
        ): Double {
            // Simplified Sortino calculation using only negative returns
            val negativeReturns =
                (1 until series.barCount)
                    .map { i ->
                        val previousPrice = series.getBar(i - 1).closePrice.doubleValue()
                        val currentPrice = series.getBar(i).closePrice.doubleValue()
                        (currentPrice - previousPrice) / previousPrice
                    }
                    .filter { it < 0 }

            if (negativeReturns.isEmpty()) {
                return 0.0
            }

            // Calculate downside deviation
            val meanNegativeReturn = negativeReturns.average()
            val downsideDeviation =
                sqrt(
                    negativeReturns.map { (it - meanNegativeReturn).pow(2) }.average(),
                )

            // Calculate Sortino ratio using total return
            val totalReturn = calculateMetric(series, record, ReturnCriterion())
            val riskFreeRate = 0.02 // Assume 2% risk-free rate

            return if (downsideDeviation == 0.0) 0.0 else (totalReturn - riskFreeRate) / downsideDeviation
        }

        private fun calculateScore(
            sharpeRatio: Double,
            maxDrawdown: Double,
            winRate: Double,
            annualizedReturn: Double,
            profitFactor: Double,
        ): Double =
            0.25 * normalize(sharpeRatio) + // Risk-adjusted returns
                0.20 * (1 - maxDrawdown) + // Capital preservation
                0.20 * winRate + // Consistency
                0.20 * normalize(annualizedReturn) + // Absolute returns
                0.15 * normalize(profitFactor) // Profit efficiency

        private fun normalize(value: Double): Double {
            // Simple min-max normalization with reasonable bounds
            val min = -1.0
            val max = 2.0
            return ((value - min) / (max - min)).coerceIn(0.0, 1.0)
        }
    }
