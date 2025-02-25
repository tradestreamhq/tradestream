package com.verlumen.tradestream.backtesting;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.common.collect.ImmutableList;
import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyManager;
import com.verlumen.tradestream.ta4j.BarSeriesBuilder;
import org.ta4j.core.AnalysisCriterion;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseTradingRecord;
import org.ta4j.core.Strategy;
import org.ta4j.core.TradingRecord;
import org.ta4j.core.criteria.pnl.ReturnCriterion;
import org.ta4j.core.criteria.pnl.ProfitLossCriterion;
import org.ta4j.core.criteria.pnl.ProfitLossRatioCriterion;
import org.ta4j.core.num.Num;
import java.util.ArrayList;
import java.util.List;

/**
 * Implementation of BacktestRunner that evaluates trading strategies using Ta4j.
 */
final class BacktestRunnerImpl implements BacktestRunner {
    // Default timeframes to evaluate (in number of bars)
    private static final int[] DEFAULT_TIMEFRAMES = {
        60,     // 1 hour (assuming 1-minute bars)
        240,    // 4 hours
        1440,   // 1 day
        10080   // 1 week
    };

    private final StrategyManager strategyManager;

    @Inject
    BacktestRunnerImpl(StrategyManager strategyManager) {
        this.strategyManager = strategyManager;
    }

    @Override
    public BacktestResult runBacktest(BacktestRequest request) throws InvalidProtocolBufferException {
        checkArgument(request.getCandlesList().size() > 0, "Bar series cannot be empty");
        BarSeries series = BarSeriesBuilder.createBarSeries(
            ImmutableList.copyOf(request.getCandlesList())
        );
        Strategy strategy = strategyManager.createStrategy(
            series,  request.getStrategy().getType(),request.getStrategy().getParameters()
        );
        
        List<TimeframeResult> timeframeResults = new ArrayList<>();
        
        // Always evaluate the full series timeframe first
        TimeframeResult fullSeriesResult = evaluateTimeframe(
            series,
            strategy,
            series.getBarCount()
        );
        timeframeResults.add(fullSeriesResult);
        
        // Then evaluate additional standard timeframes if we have enough data
        for (int timeframe : DEFAULT_TIMEFRAMES) {
            if (timeframe < series.getBarCount()) {
                TimeframeResult result = evaluateTimeframe(
                    series, strategy, timeframe
                );
                timeframeResults.add(result);
            }
        }

        // Calculate overall score as weighted average of timeframe results
        double overallScore = calculateOverallScore(timeframeResults);

        return BacktestResult.newBuilder()
            .addAllTimeframeResults(timeframeResults)
            .setOverallScore(overallScore)
            .build();
    }

    private TimeframeResult evaluateTimeframe(BarSeries series, Strategy strategy, int timeframe) {
        // Get the subseries for this timeframe
        int startIndex = Math.max(0, series.getBarCount() - timeframe);
        BarSeries timeframeSeries = series.getSubSeries(startIndex, series.getBarCount());
        
        // Run the strategy
        TradingRecord tradingRecord = runStrategy(timeframeSeries, strategy);

        // Calculate basic metrics
        double cumulativeReturn = calculateMetric(timeframeSeries, tradingRecord, 
            new ProfitLossCriterion());
        
        double profitFactor = calculateMetric(timeframeSeries, tradingRecord,
            new ProfitLossRatioCriterion());
        
        double annualizedReturn = calculateAnnualizedReturn(timeframeSeries, tradingRecord);
        
        // Calculate risk metrics
        double volatility = calculateVolatility(timeframeSeries);
        double maxDrawdown = calculateMaxDrawdown(timeframeSeries);
        
        // Trade statistics
        int numberOfTrades = tradingRecord.getPositions().size();
        double winRate = calculateWinRate(timeframeSeries, tradingRecord);
        double averageTradeDuration = calculateAverageTradeDuration(tradingRecord);

        // Risk-adjusted returns
        double sharpeRatio = calculateSharpeRatio(cumulativeReturn, volatility);
        double sortinoRatio = calculateSortinoRatio(timeframeSeries, tradingRecord);

        // Alpha/Beta (simplified calculation)
        double alpha = 0.0; // TODO: Implement when benchmark data is available
        double beta = 1.0;  // TODO: Implement when benchmark data is available

        return TimeframeResult.newBuilder()
            .setTimeframe(String.valueOf(timeframe))
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
            .build();
    }

    private TradingRecord runStrategy(BarSeries series, Strategy strategy) {
        TradingRecord tradingRecord = new BaseTradingRecord();
        
        // Skip unstable period at the start
        for (int i = strategy.getUnstableBars(); i < series.getBarCount(); i++) {
            // Check if we should enter long position
            if (strategy.shouldEnter(i)) {
                // Enter with a position size of 1 unit
                tradingRecord.enter(i, series.getBar(i).getClosePrice(), series.numOf(1));
            }
            // Check if we should exit an open position
            else if (strategy.shouldExit(i) && tradingRecord.getCurrentPosition().isOpened()) {
                tradingRecord.exit(i, series.getBar(i).getClosePrice(), series.numOf(1));
            }
        }
        
        return tradingRecord;
    }

    private double calculateMetric(BarSeries series, TradingRecord record,
            AnalysisCriterion criterion) {
        return criterion.calculate(series, record).doubleValue();
    }

    private double calculateVolatility(BarSeries series) {
        if (series.getBarCount() < 2) {
            return 0.0;
        }

        List<Double> returns = new ArrayList<>();
        for (int i = 1; i < series.getBarCount(); i++) {
            Num previousClose = series.getBar(i - 1).getClosePrice();
            Num currentClose = series.getBar(i).getClosePrice();
            double dailyReturn = currentClose.minus(previousClose)
                .dividedBy(previousClose)
                .doubleValue();
            returns.add(dailyReturn);
        }
        
        // Calculate standard deviation
        double mean = returns.stream()
            .mapToDouble(Double::doubleValue)
            .average()
            .orElse(0.0);
            
        double variance = returns.stream()
            .mapToDouble(r -> Math.pow(r - mean, 2))
            .average()
            .orElse(0.0);
            
        return Math.sqrt(variance);
    }

    private double calculateMaxDrawdown(BarSeries series) {
        if (series.getBarCount() == 0) {
            return 0.0;
        }

        double maxDrawdown = 0.0;
        double peak = series.getBar(0).getClosePrice().doubleValue();
        
        for (int i = 1; i < series.getBarCount(); i++) {
            double price = series.getBar(i).getClosePrice().doubleValue();
            
            if (price > peak) {
                peak = price;
            }
            
            double drawdown = (peak - price) / peak;
            maxDrawdown = Math.max(maxDrawdown, drawdown);
        }
        
        return maxDrawdown;
    }

    private double calculateWinRate(BarSeries series, TradingRecord record) {
        if (record.getPositions().isEmpty()) {
            return 0.0;
        }

        long winningTrades = record.getPositions().stream()
            .filter(position -> position.isClosed() && 
                position.getProfit().isPositive())
            .count();
        
        return (double) winningTrades / record.getPositions().size();
    }

    private double calculateAverageTradeDuration(TradingRecord record) {
        if (record.getPositions().isEmpty()) {
            return 0.0;
        }

        double totalDuration = record.getPositions().stream()
            .filter(position -> position.isClosed())
            .mapToInt(position -> position.getExit().getIndex() - position.getEntry().getIndex())
            .sum();
        
        long closedPositions = record.getPositions().stream()
            .filter(position -> position.isClosed())
            .count();
        
        return closedPositions > 0 ? totalDuration / closedPositions : 0.0;
    }

    private double calculateAnnualizedReturn(BarSeries series, TradingRecord record) {
        double totalReturn = calculateMetric(series, record, new ReturnCriterion());
        int barsPerYear = 252 * 1440; // Assuming 1-minute bars and 252 trading days
        double years = (double) series.getBarCount() / barsPerYear;
        
        // Use compound annual growth rate formula
        return Math.pow(1 + totalReturn, 1 / years) - 1;
    }

    private double calculateSharpeRatio(double returns, double volatility) {
        double riskFreeRate = 0.02; // Assume 2% risk-free rate
        return volatility == 0 ? 0 : (returns - riskFreeRate) / volatility;
    }

    private double calculateSortinoRatio(BarSeries series, TradingRecord record) {
        // Simplified Sortino calculation using only negative returns
        List<Double> negativeReturns = new ArrayList<>();
        
        for (int i = 1; i < series.getBarCount(); i++) {
            double previousPrice = series.getBar(i - 1).getClosePrice().doubleValue();
            double currentPrice = series.getBar(i).getClosePrice().doubleValue();
            double return_ = (currentPrice - previousPrice) / previousPrice;
            
            if (return_ < 0) {
                negativeReturns.add(return_);
            }
        }
        
        if (negativeReturns.isEmpty()) {
            return 0.0;
        }
        
        // Calculate downside deviation
        double meanNegativeReturn = negativeReturns.stream()
            .mapToDouble(Double::doubleValue)
            .average()
            .orElse(0.0);
            
        double downsideDeviation = Math.sqrt(
            negativeReturns.stream()
                .mapToDouble(r -> Math.pow(r - meanNegativeReturn, 2))
                .average()
                .orElse(0.0)
        );
        
        // Calculate Sortino ratio using total return
        double totalReturn = calculateMetric(series, record, new ReturnCriterion());
        double riskFreeRate = 0.02; // Assume 2% risk-free rate
        
        return downsideDeviation == 0 ? 0 : (totalReturn - riskFreeRate) / downsideDeviation;
    }

    private double calculateOverallScore(List<TimeframeResult> results) {
        if (results.isEmpty()) {
            return 0.0;
        }

        double totalScore = 0.0;
        for (TimeframeResult result : results) {
            // Weight different metrics based on their importance
            double timeframeScore = 
                0.25 * normalize(result.getSharpeRatio()) +          // Risk-adjusted returns
                0.20 * (1 - result.getMaxDrawdown()) +              // Capital preservation
                0.20 * result.getWinRate() +                        // Consistency
                0.20 * normalize(result.getAnnualizedReturn()) +    // Absolute returns
                0.15 * normalize(result.getProfitFactor());         // Profit efficiency
                
            totalScore += timeframeScore;
        }
        
        return totalScore / results.size();
    }

    private double normalize(double value) {
        // Simple min-max normalization with reasonable bounds
        double min = -1.0;
        double max = 2.0;
        return Math.max(0, Math.min(1, (value - min) / (max - min)));
    }
}
