package com.verlumen.tradestream.strategies.rangebars;

import com.verlumen.tradestream.strategies.RangeBarsParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;

public final class RangeBarsStrategyFactory implements StrategyFactory<RangeBarsParameters> {
  @Override
  public RangeBarsParameters getDefaultParameters() {
    return RangeBarsParameters.newBuilder().setRangeSize(1.0).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, RangeBarsParameters parameters) {
    // TODO: Implement the actual Range Bars strategy logic using TA4J or custom indicators.
    // For now, return a dummy strategy to satisfy the interface.
    return new org.ta4j.core.Strategy() {
      @Override
      public boolean shouldEnter(int index) {
        return false;
      }

      @Override
      public boolean shouldExit(int index) {
        return false;
      }

      @Override
      public String getName() {
        return "RangeBarsDummy";
      }

      @Override
      public boolean isUnstableAt(int index) {
        return false;
      }

      @Override
      public int getUnstableBars() {
        return 0;
      }

      @Override
      public void setUnstableBars(int unstableBars) {
        /* no-op for dummy */
      }

      @Override
      public Strategy opposite() {
        return this;
      }

      @Override
      public Strategy or(String name, Strategy other, int unstableBars) {
        return this;
      }

      @Override
      public Strategy and(String name, Strategy other, int unstableBars) {
        return this;
      }

      @Override
      public Strategy or(Strategy other) {
        return this;
      }

      @Override
      public Strategy and(Strategy other) {
        return this;
      }

      @Override
      public Rule getEntryRule() {
        return null;
      }

      @Override
      public Rule getExitRule() {
        return null;
      }
    };
  }
}
