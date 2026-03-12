package com.verlumen.tradestream.strategies.cmomfi;

import com.verlumen.tradestream.strategies.CmoMfiParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.VolumeIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

@Deprecated
public final class CmoMfiStrategyFactory implements StrategyFactory<CmoMfiParameters> {

  @Override
  public CmoMfiParameters getDefaultParameters() {
    return CmoMfiParameters.newBuilder().setCmoPeriod(14).setMfiPeriod(14).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, CmoMfiParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    HighPriceIndicator highPrice = new HighPriceIndicator(series);
    LowPriceIndicator lowPrice = new LowPriceIndicator(series);
    VolumeIndicator volume = new VolumeIndicator(series);

    // Calculate CMO (Chande Momentum Oscillator)
    CmoIndicator cmo = new CmoIndicator(closePrice, parameters.getCmoPeriod());

    // Calculate MFI (Money Flow Index)
    MfiIndicator mfi =
        new MfiIndicator(highPrice, lowPrice, closePrice, volume, parameters.getMfiPeriod());

    // Entry rules: CMO crosses above 0 and MFI is oversold (below 20)
    var entryRule =
        new CrossedUpIndicatorRule(cmo, cmo.getBarSeries().numFactory().numOf(0))
            .and(new UnderIndicatorRule(mfi, mfi.getBarSeries().numFactory().numOf(20)));

    // Exit rules: CMO crosses below 0 or MFI is overbought (above 80)
    var exitRule =
        new CrossedDownIndicatorRule(cmo, cmo.getBarSeries().numFactory().numOf(0))
            .or(new OverIndicatorRule(mfi, mfi.getBarSeries().numFactory().numOf(80)));

    return new org.ta4j.core.BaseStrategy(
        "CmoMfi",
        entryRule,
        exitRule,
        Math.max(parameters.getCmoPeriod(), parameters.getMfiPeriod()));
  }

  /**
   * Custom indicator that calculates the Chande Momentum Oscillator (CMO). CMO measures the
   * momentum of price changes over a specified period.
   */
  private static class CmoIndicator extends CachedIndicator<Num> {
    private final ClosePriceIndicator closePrice;
    private final int period;

    public CmoIndicator(ClosePriceIndicator closePrice, int period) {
      super(closePrice);
      this.closePrice = closePrice;
      this.period = period;
    }

    @Override
    protected Num calculate(int index) {
      if (index < period) {
        return getBarSeries().numFactory().numOf(0);
      }

      Num sumGains = getBarSeries().numFactory().numOf(0);
      Num sumLosses = getBarSeries().numFactory().numOf(0);

      for (int i = index - period + 1; i <= index; i++) {
        Num change = closePrice.getValue(i).minus(closePrice.getValue(i - 1));
        if (change.isGreaterThan(getBarSeries().numFactory().numOf(0))) {
          sumGains = sumGains.plus(change);
        } else {
          sumLosses = sumLosses.plus(change.abs());
        }
      }

      Num total = sumGains.plus(sumLosses);
      if (total.isZero()) {
        return getBarSeries().numFactory().numOf(0);
      }

      return sumGains.minus(sumLosses).dividedBy(total).multipliedBy(getBarSeries().numFactory().numOf(100));
    }

    @Override
    public int getCountOfUnstableBars() {
      return period;
    }
  }

  /**
   * Custom indicator that calculates the Money Flow Index (MFI). MFI combines price and volume to
   * measure buying and selling pressure.
   */
  private static class MfiIndicator extends CachedIndicator<Num> {
    private final HighPriceIndicator highPrice;
    private final LowPriceIndicator lowPrice;
    private final ClosePriceIndicator closePrice;
    private final VolumeIndicator volume;
    private final int period;

    public MfiIndicator(
        HighPriceIndicator highPrice,
        LowPriceIndicator lowPrice,
        ClosePriceIndicator closePrice,
        VolumeIndicator volume,
        int period) {
      super(highPrice);
      this.highPrice = highPrice;
      this.lowPrice = lowPrice;
      this.closePrice = closePrice;
      this.volume = volume;
      this.period = period;
    }

    @Override
    protected Num calculate(int index) {
      if (index < period) {
        return getBarSeries().numFactory().numOf(50);
      }

      Num positiveMoneyFlow = getBarSeries().numFactory().numOf(0);
      Num negativeMoneyFlow = getBarSeries().numFactory().numOf(0);

      for (int i = index - period + 1; i <= index; i++) {
        Num typicalPrice =
            highPrice
                .getValue(i)
                .plus(lowPrice.getValue(i))
                .plus(closePrice.getValue(i))
                .dividedBy(getBarSeries().numFactory().numOf(3));
        Num moneyFlow = typicalPrice.multipliedBy(volume.getValue(i));

        if (i > 0) {
          Num prevTypicalPrice =
              highPrice
                  .getValue(i - 1)
                  .plus(lowPrice.getValue(i - 1))
                  .plus(closePrice.getValue(i - 1))
                  .dividedBy(getBarSeries().numFactory().numOf(3));

          if (typicalPrice.isGreaterThan(prevTypicalPrice)) {
            positiveMoneyFlow = positiveMoneyFlow.plus(moneyFlow);
          } else if (typicalPrice.isLessThan(prevTypicalPrice)) {
            negativeMoneyFlow = negativeMoneyFlow.plus(moneyFlow);
          }
        }
      }

      Num totalMoneyFlow = positiveMoneyFlow.plus(negativeMoneyFlow);
      if (totalMoneyFlow.isZero()) {
        return getBarSeries().numFactory().numOf(50);
      }

      Num moneyRatio = positiveMoneyFlow.dividedBy(negativeMoneyFlow);
      return getBarSeries().numFactory().numOf(100).minus(getBarSeries().numFactory().numOf(100).dividedBy(getBarSeries().numFactory().numOf(1).plus(moneyRatio)));
    }

    @Override
    public int getCountOfUnstableBars() {
      return period;
    }
  }
}
