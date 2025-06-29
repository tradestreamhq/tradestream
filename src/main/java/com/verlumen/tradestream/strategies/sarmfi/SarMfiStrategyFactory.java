package com.verlumen.tradestream.strategies.sarmfi;

import com.verlumen.tradestream.strategies.SarMfiParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;

public final class SarMfiStrategyFactory implements StrategyFactory<SarMfiParameters> {
  @Override
  public SarMfiParameters getDefaultParameters() {
    return SarMfiParameters.newBuilder()
        .setAccelerationFactorStart(0.02)
        .setAccelerationFactorIncrement(0.02)
        .setAccelerationFactorMax(0.2)
        .setMfiPeriod(14)
        .build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, SarMfiParameters parameters) {
    // TODO: Implement the actual SAR-MFI strategy logic using TA4J or custom indicators.
    // For now, return a dummy Strategy implementation that satisfies the interface.
    return new Strategy() {
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
        return "SarMfiDummy";
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
      public void setUnstableBars(int unstableBars) {}

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
