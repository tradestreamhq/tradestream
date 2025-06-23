package com.verlumen.tradestream.strategies.dematemacrossover;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DemaTemaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class DemaTemaCrossoverStrategyFactory
    implements StrategyFactory<DemaTemaCrossoverParameters> {

  @Override
  public Strategy createStrategy(BarSeries series, DemaTemaCrossoverParameters params)
      throws InvalidProtocolBufferException {
    checkArgument(params.getDemaPeriod() > 0, "DEMA period must be positive");
    checkArgument(params.getTemaPeriod() > 0, "TEMA period must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);

    // Create DEMA indicator: 2 * EMA - EMA(EMA)
    DEMAIndicator dema = new DEMAIndicator(closePrice, params.getDemaPeriod());

    // Create TEMA indicator: 3 * EMA - 3 * EMA(EMA) + EMA(EMA(EMA))
    TEMAIndicator tema = new TEMAIndicator(closePrice, params.getTemaPeriod());

    // Entry rule: DEMA crosses above TEMA
    Rule entryRule = new CrossedUpIndicatorRule(dema, tema);

    // Exit rule: DEMA crosses below TEMA
    Rule exitRule = new CrossedDownIndicatorRule(dema, tema);

    // Create strategy using the constructor that takes unstable period directly
    return new BaseStrategy(
        String.format(
            "%s (%d, %d)",
            StrategyType.DEMA_TEMA_CROSSOVER.name(),
            params.getDemaPeriod(),
            params.getTemaPeriod()),
        entryRule,
        exitRule,
        Math.max(params.getDemaPeriod(), params.getTemaPeriod()));
  }

  @Override
  public DemaTemaCrossoverParameters getDefaultParameters() {
    return DemaTemaCrossoverParameters.newBuilder().setDemaPeriod(12).setTemaPeriod(26).build();
  }

  /** Double Exponential Moving Average (DEMA) indicator. DEMA = 2 * EMA - EMA(EMA) */
  private static class DEMAIndicator extends CachedIndicator<Num> {
    private final EMAIndicator ema;
    private final EMAIndicator emaOfEma;

    public DEMAIndicator(ClosePriceIndicator closePrice, int period) {
      super(closePrice);
      this.ema = new EMAIndicator(closePrice, period);
      this.emaOfEma = new EMAIndicator(ema, period);
    }

    @Override
    protected Num calculate(int index) {
      Num emaValue = ema.getValue(index);
      Num emaOfEmaValue = emaOfEma.getValue(index);
      return emaValue.multipliedBy(numOf(2)).minus(emaOfEmaValue);
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }

  /**
   * Triple Exponential Moving Average (TEMA) indicator. TEMA = 3 * EMA - 3 * EMA(EMA) +
   * EMA(EMA(EMA))
   */
  private static class TEMAIndicator extends CachedIndicator<Num> {
    private final EMAIndicator ema;
    private final EMAIndicator emaOfEma;
    private final EMAIndicator emaOfEmaOfEma;

    public TEMAIndicator(ClosePriceIndicator closePrice, int period) {
      super(closePrice);
      this.ema = new EMAIndicator(closePrice, period);
      this.emaOfEma = new EMAIndicator(ema, period);
      this.emaOfEmaOfEma = new EMAIndicator(emaOfEma, period);
    }

    @Override
    protected Num calculate(int index) {
      Num emaValue = ema.getValue(index);
      Num emaOfEmaValue = emaOfEma.getValue(index);
      Num emaOfEmaOfEmaValue = emaOfEmaOfEma.getValue(index);

      return emaValue
          .multipliedBy(numOf(3))
          .minus(emaOfEmaValue.multipliedBy(numOf(3)))
          .plus(emaOfEmaOfEmaValue);
    }

    @Override
    public int getUnstableBars() {
      return 0;
    }
  }
}
