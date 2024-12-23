package com.verlumen.tradestream.backtesting;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.inject.Inject;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.TradingRecord;
import org.ta4j.core.analysis.criteria.*;
import org.ta4j.core.num.Num;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;

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

    @Inject
    BacktestRunnerImpl() {}

    @Override
    public BacktestResult runBacktest(BacktestRequest request) {
        checkArgument(request.barSeries().getBarCount() > 0, "Bar series cannot be empty");
        
        List<TimeframeResult> timeframeResults = new ArrayList<>();
        
        // Test each timeframe
        for (int timeframe : DEFAULT_TIMEFRAMES) {
            if (timeframe <= request.barSeries().getBarCount()) {
                TimeframeResult result = evaluateTimeframe(
                    request.barSeries(),
                    request.strategy(),
                    timeframe
                );
                timeframeResults.add(result);
            }
        }

        // Calculate overall score as weighted average of timeframe results
        double overallScore = calculateOverallScore(timeframeResults);

        return BacktestResult.newBuilder()
            .setStrategyType(request.strategyType())
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

        // Calculate metrics
        double totalReturn = calculateMetric(timeframeSeries, tradingRecord, 
            new TotalReturnCriterion());
        
        double sharpeRatio = calculateMetric(timeframeSeries, tradingRecord,
            new SharpeRatioCriterion());
        
        double sortinoRatio = calculateMetric(timeframeSeries, tradingRecord,
            new SortinoRatioCriterion());
        
        double maxDrawdown = calculateMetric(timeframeSeries, tradingRecord,
            new MaxDrawdownCriterion());
            
        double volatility = calculateVolatility(timeframeSeries);
        
        int numTrades = tradingRecord.getPositions().size();
        
        double winRate = calculateWinRate(timeframeSeries, tradingRecord);
        
        double profitFactor = calculateProfitFactor(timeframeSeries, tradingRecord);
        
        double avgTradeDuration = calculateAverageTradeDuration(tradingRecord);

        // Calculate alpha and beta if benchmark data is available
        double alpha = 0.0; // TODO: Implement when benchmark data is available
        double beta = 1.0;  // TODO: Implement when benchmark data is available

        return TimeframeResult.newBuilder()
            .setTimeframe(String.valueOf(timeframe))
            .setCumulativeReturn(totalReturn)
            .setAnnualizedReturn(annualize(totalReturn, timeframe))
            .setSharpeRatio(sharpeRatio)
            .setSortinoRatio(sortinoRatio)
            .setMaxDrawdown(maxDrawdown)
            .setVolatility(volatility)
            .setWinRate(winRate)
            .setProfitFactor(profitFactor)
            .setNumberOfTrades(numTrades)
            .setAverageTradeDuration(avgTradeDuration)
            .setAlpha(alpha)
            .setBeta(beta)
            .build();
    }

    private TradingRecord runStrategy(BarSeries series, Strategy strategy) {
        TradingRecord tradingRecord = new TradingRecord();
        
        for (int i = strategy.getUnstableBars(); i < series.getBarCount(); i++) {
            if (strategy.shouldEnter(i)) {
                tradingRecord.enter(i, series.getBar(i).getClosePrice(), series.numOf(1));
            } else if (strategy.shouldExit(i)) {
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
        ReturnCriterion returns = new ReturnCriterion();
        List<Double> dailyReturns = new ArrayList<>();
        
        for (int i = 1; i < series.getBarCount(); i++) {
            Num previousClose = series.getBar(i - 1).getClosePrice();
            Num currentClose = series.getBar(i).getClosePrice();
            double dailyReturn = currentClose.minus(previousClose)
                .dividedBy(previousClose)
                .doubleValue();
            dailyReturns.add(dailyReturn);
        }
        
        // Calculate standard deviation of returns
        double mean = dailyReturns.stream()
            .mapToDouble(Double::doubleValue)
            .average()
            .orElse(0.0);
            
        double variance = dailyReturns.stream()
            .mapToDouble(r -> Math.pow(r - mean, 2))
            .average()
            .orElse(0.0);
            
        return Math.sqrt(variance);
    }

    private double calculateWinRate(BarSeries series, TradingRecord record) {
        if (record.getPositions().isEmpty()) {
            return 0.0;
        }

        int winningTrades = 0;
        for (org.ta4j.core.Position position : record.getPositions()) {
            if (position.isClosed()) {
                double entryPrice = position.getEntry().getPrice().doubleValue();
                double exitPrice = position.getExit().getPrice().doubleValue();
                if (exitPrice > entryPrice) {
                    winningTrades++;
                }
            }
        }
        
        return (double) winningTrades / record.getPositions().size();
    }

    private double calculateProfitFactor(BarSeries series, TradingRecord record) {
        double grossProfit = 0.0;
        double grossLoss = 0.0;
        
        for (org.ta4j.core.Position position : record.getPositions()) {
            if (position.isClosed()) {
                double profit = position.getProfit().doubleValue();
                if (profit > 0) {
                    grossProfit += profit;
                } else {
                    grossLoss += Math.abs(profit);
                }
            }
        }
        
        return grossLoss == 0 ? grossProfit : grossProfit / grossLoss;
    }

    private double calculateAverageTradeDuration(TradingRecord record) {
        if (record.getPositions().isEmpty()) {
            return 0.0;
        }

        double totalDuration = 0.0;
        for (org.ta4j.core.Position position : record.getPositions()) {
            if (position.isClosed()) {
                int duration = position.getExit().getIndex() - position.getEntry().getIndex();
                totalDuration += duration;
            }
        }
        
        return totalDuration / record.getPositions().size();
    }

    private double annualize(double totalReturn, int timeframe) {
        // Assuming 252 trading days per year
        double yearsElapsed = timeframe / (252.0 * 1440.0); // Convert minutes to years
        return Math.pow(1 + totalReturn, 1 / yearsElapsed) - 1;
    }

    private double calculateOverallScore(List<TimeframeResult> results) {
        if (results.isEmpty()) {
            return 0.0;
        }

        // Weight the different components
        double score = 0.0;
        for (TimeframeResult result : results) {
            double timeframeScore = 
                0.3 * result.getSharpeRatio() +           // Risk-adjusted returns
                0.2 * (1 - result.getMaxDrawdown()) +     // Capital preservation
                0.2 * result.getWinRate() +               // Consistency
                0.15 * result.getProfitFactor() +         // Profit efficiency
                0.15 * result.getAnnualizedReturn();      // Absolute returns
                
            score += timeframeScore;
        }
        
        return score / results.size();
    }
}
