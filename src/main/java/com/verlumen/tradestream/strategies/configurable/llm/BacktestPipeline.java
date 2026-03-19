package com.verlumen.tradestream.strategies.configurable.llm;

import com.verlumen.tradestream.strategies.ConfigurableStrategyParameters;
import com.verlumen.tradestream.strategies.configurable.ConfigurableStrategyFactory;
import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;
import org.ta4j.core.backtest.BarSeriesManager;
import org.ta4j.core.criteria.VersusEnterAndHoldCriterion;
import org.ta4j.core.criteria.pnl.GrossReturnCriterion;
import org.ta4j.core.num.DecimalNum;
import org.ta4j.core.num.Num;

/**
 * Backtesting pipeline for strategy configs. Builds a Ta4j strategy from config, runs it against
 * synthetic or real bar data, and returns performance metrics.
 */
public final class BacktestPipeline {
  private static final Logger logger = Logger.getLogger(BacktestPipeline.class.getName());

  /** Run a backtest of the given strategy config against the provided bar series. */
  public BacktestResult runBacktest(StrategyConfig config, BarSeries barSeries) {
    try {
      ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
      ConfigurableStrategyParameters params = factory.getDefaultParameters();
      Strategy strategy = factory.createStrategy(barSeries, params);

      BarSeriesManager manager = new BarSeriesManager(barSeries);
      org.ta4j.core.TradingRecord tradingRecord = manager.run(strategy);

      // Calculate metrics
      GrossReturnCriterion returnCriterion = new GrossReturnCriterion();
      Num grossReturn = returnCriterion.calculate(barSeries, tradingRecord);

      int numTrades = tradingRecord.getPositionCount();

      // Calculate win rate
      int wins = 0;
      for (var position : tradingRecord.getPositions()) {
        if (position.getProfit().isPositive()) {
          wins++;
        }
      }
      double winRate = numTrades > 0 ? (double) wins / numTrades : 0.0;

      // Compare vs buy and hold
      VersusEnterAndHoldCriterion vsBuyHold =
          new VersusEnterAndHoldCriterion(new GrossReturnCriterion());
      Num vsBuyHoldRatio = vsBuyHold.calculate(barSeries, tradingRecord);

      // Approximate Sharpe as gross return / (1 - winRate + 0.01) to avoid div by zero
      double sharpeApprox = (grossReturn.doubleValue() - 1.0) / Math.max(0.01, 1.0 - winRate);

      return new BacktestResult(
          config.getName(),
          grossReturn.doubleValue(),
          sharpeApprox,
          winRate,
          numTrades,
          sharpeApprox,
          vsBuyHoldRatio.doubleValue(),
          null);
    } catch (Exception e) {
      logger.log(Level.WARNING, "Backtest failed for " + config.getName(), e);
      return new BacktestResult(config.getName(), 0.0, 0.0, 0.0, 0, 0.0, 0.0, e.getMessage());
    }
  }

  /**
   * Generate synthetic bar series for backtesting. Uses a random walk with trend to simulate
   * realistic price action.
   */
  public static BarSeries generateSyntheticBars(int barCount, long seed) {
    BarSeries series = new BaseBarSeriesBuilder().withName("synthetic").build();

    java.util.Random rng = new java.util.Random(seed);
    double price = 100.0;
    double volume = 1000000.0;

    ZonedDateTime time = ZonedDateTime.now().minusDays(barCount);

    for (int i = 0; i < barCount; i++) {
      // Random walk with slight upward drift
      double change = (rng.nextGaussian() * 0.02) + 0.0002;
      double open = price;
      double high = price * (1 + Math.abs(rng.nextGaussian() * 0.015));
      double low = price * (1 - Math.abs(rng.nextGaussian() * 0.015));
      price = price * (1 + change);
      double close = price;
      double vol = volume * (0.5 + rng.nextDouble());

      // Ensure high >= max(open, close) and low <= min(open, close)
      high = Math.max(high, Math.max(open, close));
      low = Math.min(low, Math.min(open, close));

      Instant beginTime = time.toInstant();
      Instant endTime = time.plusDays(1).toInstant();

      series.addBar(
          new BaseBar(
              Duration.ofDays(1),
              beginTime,
              endTime,
              DecimalNum.valueOf(open),
              DecimalNum.valueOf(high),
              DecimalNum.valueOf(low),
              DecimalNum.valueOf(close),
              DecimalNum.valueOf(vol),
              DecimalNum.valueOf(0),
              0));

      time = time.plusDays(1);
    }

    return series;
  }

  /** Backtest result for a single strategy. */
  public static final class BacktestResult {
    private final String strategyName;
    private final double grossReturn;
    private final double sharpeApprox;
    private final double winRate;
    private final int numTrades;
    private final double returnOverMaxDrawdown;
    private final double vsBuyHoldRatio;
    private final String error;

    public BacktestResult(
        String strategyName,
        double grossReturn,
        double sharpeApprox,
        double winRate,
        int numTrades,
        double returnOverMaxDrawdown,
        double vsBuyHoldRatio,
        String error) {
      this.strategyName = strategyName;
      this.grossReturn = grossReturn;
      this.sharpeApprox = sharpeApprox;
      this.winRate = winRate;
      this.numTrades = numTrades;
      this.returnOverMaxDrawdown = returnOverMaxDrawdown;
      this.vsBuyHoldRatio = vsBuyHoldRatio;
      this.error = error;
    }

    public String getStrategyName() {
      return strategyName;
    }

    public double getGrossReturn() {
      return grossReturn;
    }

    public double getSharpeApprox() {
      return sharpeApprox;
    }

    public double getWinRate() {
      return winRate;
    }

    public int getNumTrades() {
      return numTrades;
    }

    public double getReturnOverMaxDrawdown() {
      return returnOverMaxDrawdown;
    }

    public double getVsBuyHoldRatio() {
      return vsBuyHoldRatio;
    }

    public String getError() {
      return error;
    }

    public boolean isSuccessful() {
      return error == null;
    }

    @Override
    public String toString() {
      if (error != null) {
        return String.format("BacktestResult{%s, ERROR: %s}", strategyName, error);
      }
      return String.format(
          "BacktestResult{%s, return=%.4f, sharpe=%.4f, winRate=%.2f%%, trades=%d, vs_b&h=%.4f}",
          strategyName, grossReturn, sharpeApprox, winRate * 100, numTrades, vsBuyHoldRatio);
    }
  }
}
