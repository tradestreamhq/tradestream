package com.verlumen.tradestream.strategies.ichimokucloud;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.IchimokuCloudParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class IchimokuCloudStrategyFactory
    implements StrategyFactory<IchimokuCloudParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, IchimokuCloudParameters params) {
    checkArgument(params.getTenkanSenPeriod() > 0, "Tenkan-sen period must be positive");
    checkArgument(params.getKijunSenPeriod() > 0, "Kijun-sen period must be positive");
    checkArgument(params.getSenkouSpanBPeriod() > 0, "Senkou Span B period must be positive");
    checkArgument(params.getChikouSpanPeriod() > 0, "Chikou Span period must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    // Create individual Ichimoku indicators
    TenkanSenIndicator tenkanSen = new TenkanSenIndicator(series, params.getTenkanSenPeriod());
    KijunSenIndicator kijunSen = new KijunSenIndicator(series, params.getKijunSenPeriod());
    SenkouSpanAIndicator senkouSpanA = new SenkouSpanAIndicator(tenkanSen, kijunSen);
    SenkouSpanBIndicator senkouSpanB =
        new SenkouSpanBIndicator(series, params.getSenkouSpanBPeriod());
    KumoCloudIndicator kumoCloud = new KumoCloudIndicator(senkouSpanA, senkouSpanB);

    // Entry rule: Buy when Tenkan-sen crosses above Kijun-sen and price is above the cloud
    Rule entryRule =
        new CrossedUpIndicatorRule(tenkanSen, kijunSen)
            .and(new OverIndicatorRule(closePrice, kumoCloud));

    // Exit rule: Sell when Tenkan-sen crosses below Kijun-sen or price falls below the cloud
    Rule exitRule =
        new CrossedUpIndicatorRule(kijunSen, tenkanSen)
            .or(new UnderIndicatorRule(closePrice, kumoCloud));

    return new BaseStrategy(
        String.format(
            "%s (Tenkan: %d, Kijun: %d, SenkouB: %d, Chikou: %d)",
            StrategyType.ICHIMOKU_CLOUD.name(),
            params.getTenkanSenPeriod(),
            params.getKijunSenPeriod(),
            params.getSenkouSpanBPeriod(),
            params.getChikouSpanPeriod()),
        entryRule,
        exitRule,
        params.getSenkouSpanBPeriod()); // Use Senkou Span B period as unstable period
  }

  @Override
  public IchimokuCloudParameters getDefaultParameters() {
    return IchimokuCloudParameters.newBuilder()
        .setTenkanSenPeriod(9) // Standard Tenkan-sen period
        .setKijunSenPeriod(26) // Standard Kijun-sen period
        .setSenkouSpanBPeriod(52) // Standard Senkou Span B period
        .setChikouSpanPeriod(26) // Standard Chikou Span period
        .build();
  }

  /** Tenkan-sen (Conversion Line) = (9-period high + 9-period low) / 2 */
  private static class TenkanSenIndicator extends CachedIndicator<Num> {
    private final HighPriceIndicator highPrice;
    private final LowPriceIndicator lowPrice;
    private final int period;

    public TenkanSenIndicator(BarSeries series, int period) {
      super(series);
      this.highPrice = new HighPriceIndicator(series);
      this.lowPrice = new LowPriceIndicator(series);
      this.period = period;
    }

    @Override
    protected Num calculate(int index) {
      if (index < period - 1) {
        return numOf(0);
      }

      Num highestHigh = highPrice.getValue(index - period + 1);
      Num lowestLow = lowPrice.getValue(index - period + 1);

      for (int i = index - period + 2; i <= index; i++) {
        Num currentHigh = highPrice.getValue(i);
        Num currentLow = lowPrice.getValue(i);
        if (currentHigh.isGreaterThan(highestHigh)) {
          highestHigh = currentHigh;
        }
        if (currentLow.isLessThan(lowestLow)) {
          lowestLow = currentLow;
        }
      }

      return highestHigh.plus(lowestLow).dividedBy(numOf(2));
    }

    @Override
    public int getUnstableBars() {
      return period;
    }
  }

  /** Kijun-sen (Base Line) = (26-period high + 26-period low) / 2 */
  private static class KijunSenIndicator extends CachedIndicator<Num> {
    private final HighPriceIndicator highPrice;
    private final LowPriceIndicator lowPrice;
    private final int period;

    public KijunSenIndicator(BarSeries series, int period) {
      super(series);
      this.highPrice = new HighPriceIndicator(series);
      this.lowPrice = new LowPriceIndicator(series);
      this.period = period;
    }

    @Override
    protected Num calculate(int index) {
      if (index < period - 1) {
        return numOf(0);
      }

      Num highestHigh = highPrice.getValue(index - period + 1);
      Num lowestLow = lowPrice.getValue(index - period + 1);

      for (int i = index - period + 2; i <= index; i++) {
        Num currentHigh = highPrice.getValue(i);
        Num currentLow = lowPrice.getValue(i);
        if (currentHigh.isGreaterThan(highestHigh)) {
          highestHigh = currentHigh;
        }
        if (currentLow.isLessThan(lowestLow)) {
          lowestLow = currentLow;
        }
      }

      return highestHigh.plus(lowestLow).dividedBy(numOf(2));
    }

    @Override
    public int getUnstableBars() {
      return period;
    }
  }

  /** Senkou Span A (Leading Span A) = (Tenkan-sen + Kijun-sen) / 2, shifted 26 periods ahead */
  private static class SenkouSpanAIndicator extends CachedIndicator<Num> {
    private final TenkanSenIndicator tenkanSen;
    private final KijunSenIndicator kijunSen;

    public SenkouSpanAIndicator(TenkanSenIndicator tenkanSen, KijunSenIndicator kijunSen) {
      super(tenkanSen);
      this.tenkanSen = tenkanSen;
      this.kijunSen = kijunSen;
    }

    @Override
    protected Num calculate(int index) {
      // Senkou Span A is shifted 26 periods ahead
      int shiftedIndex = index + 26;
      if (shiftedIndex >= getBarSeries().getBarCount()) {
        return numOf(0);
      }

      Num tenkanValue = tenkanSen.getValue(shiftedIndex);
      Num kijunValue = kijunSen.getValue(shiftedIndex);
      return tenkanValue.plus(kijunValue).dividedBy(numOf(2));
    }

    @Override
    public int getUnstableBars() {
      return Math.max(tenkanSen.getUnstableBars(), kijunSen.getUnstableBars()) + 26;
    }
  }

  /**
   * Senkou Span B (Leading Span B) = (52-period high + 52-period low) / 2, shifted 26 periods ahead
   */
  private static class SenkouSpanBIndicator extends CachedIndicator<Num> {
    private final HighPriceIndicator highPrice;
    private final LowPriceIndicator lowPrice;
    private final int period;

    public SenkouSpanBIndicator(BarSeries series, int period) {
      super(series);
      this.highPrice = new HighPriceIndicator(series);
      this.lowPrice = new LowPriceIndicator(series);
      this.period = period;
    }

    @Override
    protected Num calculate(int index) {
      // Senkou Span B is shifted 26 periods ahead
      int shiftedIndex = index + 26;
      if (shiftedIndex < period - 1 || shiftedIndex >= getBarSeries().getBarCount()) {
        return numOf(0);
      }

      Num highestHigh = highPrice.getValue(shiftedIndex - period + 1);
      Num lowestLow = lowPrice.getValue(shiftedIndex - period + 1);

      for (int i = shiftedIndex - period + 2; i <= shiftedIndex; i++) {
        Num currentHigh = highPrice.getValue(i);
        Num currentLow = lowPrice.getValue(i);
        if (currentHigh.isGreaterThan(highestHigh)) {
          highestHigh = currentHigh;
        }
        if (currentLow.isLessThan(lowestLow)) {
          lowestLow = currentLow;
        }
      }

      return highestHigh.plus(lowestLow).dividedBy(numOf(2));
    }

    @Override
    public int getUnstableBars() {
      return period + 26;
    }
  }

  /** Kumo Cloud - represents the area between Senkou Span A and Senkou Span B */
  private static class KumoCloudIndicator extends CachedIndicator<Num> {
    private final SenkouSpanAIndicator senkouSpanA;
    private final SenkouSpanBIndicator senkouSpanB;

    public KumoCloudIndicator(SenkouSpanAIndicator senkouSpanA, SenkouSpanBIndicator senkouSpanB) {
      super(senkouSpanA);
      this.senkouSpanA = senkouSpanA;
      this.senkouSpanB = senkouSpanB;
    }

    @Override
    protected Num calculate(int index) {
      Num spanA = senkouSpanA.getValue(index);
      Num spanB = senkouSpanB.getValue(index);
      // Return the higher of the two spans as the cloud boundary
      return spanA.isGreaterThan(spanB) ? spanA : spanB;
    }

    @Override
    public int getUnstableBars() {
      return Math.max(senkouSpanA.getUnstableBars(), senkouSpanB.getUnstableBars());
    }
  }
}