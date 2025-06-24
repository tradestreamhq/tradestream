package com.verlumen.tradestream.strategies.rocma;

import com.verlumen.tradestream.strategies.RocMaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Indicator;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class RocMaCrossoverStrategyFactory
    implements StrategyFactory<RocMaCrossoverParameters> {

  @Override
  public RocMaCrossoverParameters getDefaultParameters() {
    return RocMaCrossoverParameters.newBuilder().setRocPeriod(10).setMaPeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, RocMaCrossoverParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);

    // Rate of Change (ROC) indicator
    RocIndicator roc = new RocIndicator(closePrice, parameters.getRocPeriod());

    // Moving Average of ROC
    EMAIndicator rocMa = new EMAIndicator(roc, parameters.getMaPeriod());

    // Entry rule: ROC crosses above its moving average
    Rule entryRule = new CrossedUpIndicatorRule(roc, rocMa);

    // Exit rule: ROC crosses below its moving average
    Rule exitRule = new CrossedDownIndicatorRule(roc, rocMa);

    return new BaseStrategy(
        "ROC_MA_CROSSOVER",
        entryRule,
        exitRule,
        Math.max(parameters.getRocPeriod(), parameters.getMaPeriod()));
  }

  /**
   * Custom Rate of Change (ROC) indicator. ROC = ((Current Price - Price n periods ago) / Price n
   * periods ago) * 100
   */
  private static class RocIndicator extends org.ta4j.core.indicators.CachedIndicator<Num> {
    private final Indicator<Num> priceIndicator;
    private final int period;

    public RocIndicator(Indicator<Num> priceIndicator, int period) {
      super(priceIndicator);
      this.priceIndicator = priceIndicator;
      this.period = period;
    }

    @Override
    protected Num calculate(int index) {
      if (index < period) {
        return numOf(0);
      }

      Num currentPrice = priceIndicator.getValue(index);
      Num pastPrice = priceIndicator.getValue(index - period);

      if (pastPrice.isZero()) {
        return numOf(0);
      }

      return currentPrice.minus(pastPrice).dividedBy(pastPrice).multipliedBy(numOf(100));
    }

    @Override
    public BarSeries getBarSeries() {
      return priceIndicator.getBarSeries();
    }

    @Override
    public int getUnstableBars() {
      return period;
    }
  }
}
