package com.verlumen.tradestream.strategies.heikenashi;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.HeikenAshiParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class HeikenAshiStrategyFactory implements StrategyFactory<HeikenAshiParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, HeikenAshiParameters params) {
    checkArgument(params.getPeriod() > 0, "Period must be positive");

    HeikenAshiIndicator heikenAshi = new HeikenAshiIndicator(series, params.getPeriod());
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);

    // Entry rule: Buy when Heiken Ashi close crosses above open
    Rule entryRule = new CrossedUpIndicatorRule(heikenAshi.getClose(), heikenAshi.getOpen());
    // Exit rule: Sell when Heiken Ashi close crosses below open
    Rule exitRule = new CrossedDownIndicatorRule(heikenAshi.getClose(), heikenAshi.getOpen());

    return new BaseStrategy(
        String.format("%s (Period: %d)", StrategyType.HEIKEN_ASHI.name(), params.getPeriod()),
        entryRule,
        exitRule,
        params.getPeriod());
  }

  @Override
  public HeikenAshiParameters getDefaultParameters() {
    return HeikenAshiParameters.newBuilder().setPeriod(14).build();
  }

  // Minimal Heiken Ashi indicator implementation for open/close
  private static class HeikenAshiIndicator {
    private final BarSeries series;
    private final int period;

    public HeikenAshiIndicator(BarSeries series, int period) {
      this.series = series;
      this.period = period;
    }

    public Indicator getOpen() {
      return new Indicator(series, period, true);
    }

    public Indicator getClose() {
      return new Indicator(series, period, false);
    }

    // Inner class for open/close values
    private static class Indicator extends org.ta4j.core.indicators.CachedIndicator<Num> {
      private final BarSeries series;
      private final int period;
      private final boolean isOpen;

      public Indicator(BarSeries series, int period, boolean isOpen) {
        super(series);
        this.series = series;
        this.period = period;
        this.isOpen = isOpen;
      }

      @Override
      protected Num calculate(int index) {
        if (index == 0) {
          return series.getBar(0).getOpenPrice();
        }
        Num prevOpen = series.getBar(index - 1).getOpenPrice();
        Num prevClose = series.getBar(index - 1).getClosePrice();
        Num open = prevOpen.plus(prevClose).dividedBy(series.numOf(2));
        Num close =
            series
                .getBar(index)
                .getOpenPrice()
                .plus(series.getBar(index).getHighPrice())
                .plus(series.getBar(index).getLowPrice())
                .plus(series.getBar(index).getClosePrice())
                .dividedBy(series.numOf(4));
        return isOpen ? open : close;
      }

      @Override
      public int getUnstableBars() {
        return period;
      }
    }
  }
}
