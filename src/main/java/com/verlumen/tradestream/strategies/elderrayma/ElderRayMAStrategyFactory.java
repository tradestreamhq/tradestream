package com.verlumen.tradestream.strategies.elderrayma;

import com.verlumen.tradestream.strategies.ElderRayMAParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Indicator;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class ElderRayMAStrategyFactory implements StrategyFactory<ElderRayMAParameters> {
  @Override
  public ElderRayMAParameters getDefaultParameters() {
    return ElderRayMAParameters.newBuilder().setEmaPeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, ElderRayMAParameters parameters) {
    int emaPeriod = parameters.getEmaPeriod();
    ClosePriceIndicator close = new ClosePriceIndicator(series);
    HighPriceIndicator high = new HighPriceIndicator(series);
    LowPriceIndicator low = new LowPriceIndicator(series);
    EMAIndicator ema = new EMAIndicator(close, emaPeriod);

    // Bull Power = High - EMA
    // Bear Power = Low - EMA
    DifferenceIndicator bullPower = new DifferenceIndicator(high, ema);
    DifferenceIndicator bearPower = new DifferenceIndicator(low, ema);

    // Entry: Bull Power crosses up 0 (bullish)
    Rule entryRule = new CrossedUpIndicatorRule(bullPower, series.numOf(0));
    // Exit: Bear Power crosses down 0 (bearish)
    Rule exitRule = new CrossedDownIndicatorRule(bearPower, series.numOf(0));

    return new BaseStrategy("ElderRayMA", entryRule, exitRule);
  }

  // Custom indicator for difference between two indicators
  private static class DifferenceIndicator implements Indicator<Num> {
    private final Indicator<Num> a;
    private final Indicator<Num> b;

    public DifferenceIndicator(Indicator<Num> a, Indicator<Num> b) {
      this.a = a;
      this.b = b;
    }

    @Override
    public Num getValue(int index) {
      return a.getValue(index).minus(b.getValue(index));
    }

    @Override
    public BarSeries getBarSeries() {
      return a.getBarSeries();
    }

    @Override
    public int getUnstableBars() {
      return Math.max(a.getUnstableBars(), b.getUnstableBars());
    }
  }
}
