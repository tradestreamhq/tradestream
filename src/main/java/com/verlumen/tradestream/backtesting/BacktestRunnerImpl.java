package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Position;
import org.ta4j.core.TradingRecord;
import org.ta4j.core.analysis.criteria.*;

final class BacktestRunnerImpl implements BacktestRunner {
  @Inject
  BacktestRunnerImpl() {}

  @Override
  public BacktestResult runBacktest(BacktestRequest request) {
    // Run the strategy over the bar series to get trading record
    TradingRecord tradingRecord = request.strategy().run(request.barSeries());

    // Calculate all the metrics using Ta4j criteria
    TimeframeResult timeframeResult = TimeframeResult.newBuilder()
        .setTimeframe("ALL_DATA") // Could be configurable in the future
        .setCumulativeReturn(calculateCumulativeReturn(request.barSeries(), tradingRecord))
        .setAnnualizedReturn(calculateAnnualizedReturn(request.barSeries(), tradingRecord))
        .setSharpeRatio(calculateSharpeRatio(request.barSeries(), tradingRecord))
        .setSortinoRatio(calculateSortinoRatio(request.barSeries(), tradingRecord))
        .setMaxDrawdown(calculateMaxDrawdown(request.barSeries(), tradingRecord))
        .setVolatility(calculateVolatility(request.barSeries()))
        .setWinRate(calculateWinRate(tradingRecord))
        .setProfitFactor(calculateProfitFactor(request.barSeries(), tradingRecord))
        .setNumberOfTrades(tradingRecord.getPositions().size())
        .setAverageTradeDuration(calculateAverageTradeDuration(tradingRecord))
        .setAlpha(calculateAlpha(request.barSeries(), tradingRecord))
        .setBeta(calculateBeta(request.barSeries()))
        .build();

    // Calculate overall score (could be made more sophisticated)
    double overallScore = calculateOverallScore(timeframeResult);

    return BacktestResult.newBuilder()
        .setStrategyType(request.strategyType())
        .addTimeframeResults(timeframeResult)
        .setOverallScore(overallScore)
        .build();
  }

  private double calculateCumulativeReturn(BarSeries series, TradingRecord record) {
    return new TotalReturnCriterion().calculate(series, record).doubleValue();
  }

  private double calculateAnnualizedReturn(BarSeries series, TradingRecord record) {
    return new AnnualizedReturnCriterion().calculate(series, record).doubleValue();
  }

  private double calculateSharpeRatio(BarSeries series, TradingRecord record) {
    return new SharpeRatioCriterion().calculate(series, record).doubleValue();
  }

  private double calculateSortinoRatio(BarSeries series, TradingRecord record) {
    return new SortinoRatioCriterion().calculate(series, record).doubleValue();
  }

  private double calculateMaxDrawdown(BarSeries series, TradingRecord record) {
    return new MaxDrawdownCriterion().calculate(series, record).doubleValue();
  }

  private double calculateVolatility(BarSeries series) {
    // Calculate standard deviation of returns
    return new VolatilityCriterion().calculate(series).doubleValue();
  }

  private double calculateWinRate(TradingRecord record) {
    int winCount = 0;
    int totalTrades = record.getPositions().size();
    
    if (totalTrades == 0) {
      return 0.0;
    }

    for (Position position : record.getPositions()) {
      if (position.getProfit().isPositive()) {
        winCount++;
      }
    }

    return (double) winCount / totalTrades;
  }

  private double calculateProfitFactor(BarSeries series, TradingRecord record) {
    return new ProfitLossCriterion().calculate(series, record).doubleValue();
  }

  private double calculateAverageTradeDuration(TradingRecord record) {
    if (record.getPositions().isEmpty()) {
      return 0.0;
    }

    double totalDuration = 0.0;
    for (org.ta4j.core.Position position : record.getPositions()) {
      if (position.isClosed()) {
        totalDuration += position.getExit().getIndex() - position.getEntry().getIndex();
      }
    }
    return totalDuration / record.getPositions().size();
  }

  private double calculateAlpha(BarSeries series, TradingRecord record) {
    // Simplified alpha calculation
    // Could be enhanced with proper market benchmark comparison
    return new ExpectedShortfallCriterion().calculate(series, record).doubleValue();
  }

  private double calculateBeta(BarSeries series) {
    // Simplified beta calculation
    // Could be enhanced with proper market correlation
    return new VolatilityCriterion().calculate(series).doubleValue();
  }

  private double calculateOverallScore(TimeframeResult result) {
    // This could be made more sophisticated with weighted components
    return (result.getSharpeRatio() + result.getSortinoRatio() + result.getWinRate() +
            (1 - result.getMaxDrawdown()) + result.getProfitFactor()) / 5.0;
  }
}
