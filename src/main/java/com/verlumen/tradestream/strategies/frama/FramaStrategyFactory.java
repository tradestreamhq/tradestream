package com.verlumen.tradestream.strategies.frama;

import com.verlumen.tradestream.strategies.FramaParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class FramaStrategyFactory implements StrategyFactory<FramaParameters> {

  @Override
  public Strategy createStrategy(BarSeries series, FramaParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    FramaIndicator framaIndicator =
        new FramaIndicator(series, parameters.getSc(), parameters.getFc(), parameters.getAlpha());

    Rule entryRule = new CrossedUpIndicatorRule(closePrice, framaIndicator);
    Rule exitRule = new CrossedDownIndicatorRule(closePrice, framaIndicator);

    return new BaseStrategy("FRAMA", entryRule, exitRule, framaIndicator.getUnstableBars());
  }

  @Override
  public FramaParameters getDefaultParameters() {
    return FramaParameters.newBuilder().setSc(0.5).setFc(20).setAlpha(0.5).build();
  }

  private static class FramaIndicator extends CachedIndicator<Num> {
    private final double sc;
    private final int fc;
    private final double alpha;

    public FramaIndicator(BarSeries series, double sc, int fc, double alpha) {
      super(series);
      this.sc = sc;
      this.fc = fc;
      this.alpha = alpha;
    }

    @Override
    protected Num calculate(int index) {
      if (index < fc) {
        return numOf(0);
      }

      // Calculate fractal dimension
      double fractalDimension = calculateFractalDimension(index);

      // Calculate adaptive alpha
      double adaptiveAlpha = Math.pow(fractalDimension, alpha);

      // Calculate FRAMA
      if (index == fc) {
        return getBarSeries().getBar(index).getClosePrice();
      }

      Num prevFrama = getValue(index - 1);
      Num currentPrice = getBarSeries().getBar(index).getClosePrice();

      return prevFrama.plus(currentPrice.minus(prevFrama).multipliedBy(numOf(adaptiveAlpha)));
    }

    private double calculateFractalDimension(int index) {
      // Simplified fractal dimension calculation
      // In a real implementation, this would be more complex
      double high = getBarSeries().getBar(index).getHighPrice().doubleValue();
      double low = getBarSeries().getBar(index).getLowPrice().doubleValue();
      double close = getBarSeries().getBar(index).getClosePrice().doubleValue();

      double range = high - low;
      double body = Math.abs(close - (high + low) / 2);

      if (range == 0) return 1.0;

      double ratio = body / range;
      return 1.0 + ratio * sc;
    }

    @Override
    public int getUnstableBars() {
      return fc;
    }
  }
}
