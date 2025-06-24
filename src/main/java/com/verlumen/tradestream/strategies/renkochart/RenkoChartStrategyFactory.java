package com.verlumen.tradestream.strategies.renkochart;

import com.verlumen.tradestream.strategies.RenkoChartParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.AbstractRule;

public final class RenkoChartStrategyFactory implements StrategyFactory<RenkoChartParameters> {
  @Override
  public RenkoChartParameters getDefaultParameters() {
    return RenkoChartParameters.newBuilder().setBrickSize(1.0).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, RenkoChartParameters parameters) {
    double brickSize = parameters.getBrickSize();
    ClosePriceIndicator close = new ClosePriceIndicator(series);
    Rule entryRule = new RenkoEntryRule(close, brickSize);
    Rule exitRule = new RenkoExitRule(close, brickSize);
    return new BaseStrategy("RenkoChart", entryRule, exitRule);
  }

  // Entry rule: triggers when price moves up by at least brickSize from last brick
  private static class RenkoEntryRule extends AbstractRule {
    private final ClosePriceIndicator close;
    private final double brickSize;

    RenkoEntryRule(ClosePriceIndicator close, double brickSize) {
      this.close = close;
      this.brickSize = brickSize;
    }

    @Override
    public boolean isSatisfied(int index, org.ta4j.core.TradingRecord tradingRecord) {
      if (index == 0) return false;
      double lastBrickPrice = close.getValue(0).doubleValue();
      for (int i = 1; i < index; i++) {
        double price = close.getValue(i).doubleValue();
        if (price >= lastBrickPrice + brickSize) {
          lastBrickPrice += brickSize * Math.floor((price - lastBrickPrice) / brickSize);
        } else if (price <= lastBrickPrice - brickSize) {
          lastBrickPrice -= brickSize * Math.floor((lastBrickPrice - price) / brickSize);
        }
      }
      double price = close.getValue(index).doubleValue();
      return price >= lastBrickPrice + brickSize;
    }
  }

  // Exit rule: triggers when price moves down by at least brickSize from last brick
  private static class RenkoExitRule extends AbstractRule {
    private final ClosePriceIndicator close;
    private final double brickSize;

    RenkoExitRule(ClosePriceIndicator close, double brickSize) {
      this.close = close;
      this.brickSize = brickSize;
    }

    @Override
    public boolean isSatisfied(int index, org.ta4j.core.TradingRecord tradingRecord) {
      if (index == 0) return false;
      double lastBrickPrice = close.getValue(0).doubleValue();
      for (int i = 1; i < index; i++) {
        double price = close.getValue(i).doubleValue();
        if (price >= lastBrickPrice + brickSize) {
          lastBrickPrice += brickSize * Math.floor((price - lastBrickPrice) / brickSize);
        } else if (price <= lastBrickPrice - brickSize) {
          lastBrickPrice -= brickSize * Math.floor((lastBrickPrice - price) / brickSize);
        }
      }
      double price = close.getValue(index).doubleValue();
      return price <= lastBrickPrice - brickSize;
    }
  }
}
