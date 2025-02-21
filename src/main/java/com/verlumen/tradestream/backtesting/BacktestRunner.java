package com.verlumen.tradestream.backtesting;

import com.google.auto.value.AutoValue;
import com.verlumen.tradestream.backtesting.BacktestResult;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import java.io.Serializable;

/**
 * Interface for running backtests on trading strategies.
 */
interface BacktestRunner {
  /**
   * Runs a backtest for the given strategy over the provided bar series.
   *
   * @param request Parameters and configuration for the backtest run
   * @return Results of the backtest analysis
   */
  BacktestResult runBacktest(BacktestRequest request);

  /**
   * Configuration for a backtest run.
   */
  @AutoValue
  abstract class BacktestRequest implements Serializable {
    abstract BarSeries barSeries();
    abstract Strategy strategy();
    abstract StrategyType strategyType();

    static Builder builder() {
      return new AutoValue_BacktestRunner_BacktestRequest.Builder();
    }

    @AutoValue.Builder
    abstract static class Builder {
      abstract Builder setBarSeries(BarSeries barSeries);
      abstract Builder setStrategy(Strategy strategy);
      abstract Builder setStrategyType(StrategyType strategyType);
      abstract BacktestRequest build();
    }
  }
}
