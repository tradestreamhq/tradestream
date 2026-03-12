package com.verlumen.tradestream.backtesting;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.Strategy;
import com.verlumen.tradestream.strategies.StrategySpecs;
import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * High-level backtesting framework that orchestrates loading historical data, running strategies,
 * and generating reports.
 */
public final class BacktestingFramework {
  private final BacktestRunner backtestRunner;

  public BacktestingFramework(BacktestRunner backtestRunner) {
    this.backtestRunner = backtestRunner;
  }

  /**
   * Runs a single strategy backtest using a data loader and default parameters.
   *
   * @param strategyName the registered strategy name (e.g., "SMA_RSI")
   * @param dataLoader source of historical candle data
   * @return the backtest result
   */
  public BacktestResult runBacktest(String strategyName, HistoricalDataLoader dataLoader)
      throws IOException, InvalidProtocolBufferException {
    List<Candle> candles = dataLoader.loadCandles();
    return runBacktest(strategyName, candles);
  }

  /**
   * Runs a single strategy backtest with pre-loaded candle data and default parameters.
   *
   * @param strategyName the registered strategy name
   * @param candles historical candle data
   * @return the backtest result
   */
  public BacktestResult runBacktest(String strategyName, List<Candle> candles)
      throws InvalidProtocolBufferException {
    Strategy strategy = createStrategyWithDefaults(strategyName);
    BacktestRequest request =
        BacktestRequest.newBuilder().addAllCandles(candles).setStrategy(strategy).build();
    return backtestRunner.runBacktest(request);
  }

  /**
   * Runs multiple strategies against the same dataset and returns a comparison.
   *
   * @param strategyNames list of strategy names to backtest
   * @param dataLoader source of historical candle data
   * @return map of strategy name to backtest result
   */
  public Map<String, BacktestResult> compareStrategies(
      List<String> strategyNames, HistoricalDataLoader dataLoader)
      throws IOException, InvalidProtocolBufferException {
    List<Candle> candles = dataLoader.loadCandles();
    return compareStrategies(strategyNames, candles);
  }

  /**
   * Runs multiple strategies against the same pre-loaded dataset.
   *
   * @param strategyNames list of strategy names to backtest
   * @param candles historical candle data
   * @return map of strategy name to backtest result, preserving insertion order
   */
  public Map<String, BacktestResult> compareStrategies(
      List<String> strategyNames, List<Candle> candles) throws InvalidProtocolBufferException {
    Map<String, BacktestResult> results = new LinkedHashMap<>();
    for (String name : strategyNames) {
      results.put(name, runBacktest(name, candles));
    }
    return results;
  }

  /**
   * Runs a backtest and returns a formatted text report.
   *
   * @param strategyName the strategy name
   * @param dataLoader source of historical data
   * @return formatted report string
   */
  public String runAndReport(String strategyName, HistoricalDataLoader dataLoader)
      throws IOException, InvalidProtocolBufferException {
    BacktestResult result = runBacktest(strategyName, dataLoader);
    return BacktestReport.generate(strategyName, result);
  }

  /**
   * Compares multiple strategies and returns a formatted comparison report.
   *
   * @param strategyNames strategies to compare
   * @param dataLoader source of historical data
   * @return formatted comparison report
   */
  public String compareAndReport(List<String> strategyNames, HistoricalDataLoader dataLoader)
      throws IOException, InvalidProtocolBufferException {
    Map<String, BacktestResult> results = compareStrategies(strategyNames, dataLoader);
    StringBuilder sb = new StringBuilder();
    sb.append("Strategy Comparison Report\n");
    sb.append("=".repeat(100)).append("\n");
    for (Map.Entry<String, BacktestResult> entry : results.entrySet()) {
      sb.append(BacktestReport.generateOneLine(entry.getKey(), entry.getValue())).append("\n");
    }
    sb.append("=".repeat(100)).append("\n\n");
    for (Map.Entry<String, BacktestResult> entry : results.entrySet()) {
      sb.append(BacktestReport.generate(entry.getKey(), entry.getValue())).append("\n");
    }
    return sb.toString();
  }

  private static Strategy createStrategyWithDefaults(String strategyName) {
    return Strategy.newBuilder()
        .setStrategyName(strategyName)
        .setParameters(
            Any.pack(
                StrategySpecs.getSpec(strategyName).getStrategyFactory().getDefaultParameters()))
        .build();
  }
}
