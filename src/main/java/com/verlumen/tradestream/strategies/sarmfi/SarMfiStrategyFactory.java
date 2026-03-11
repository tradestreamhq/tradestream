package com.verlumen.tradestream.strategies.sarmfi;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.SarMfiParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.ParabolicSarIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.TypicalPriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

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
    checkArgument(
        parameters.getAccelerationFactorStart() > 0, "Acceleration factor start must be positive");
    checkArgument(
        parameters.getAccelerationFactorIncrement() > 0,
        "Acceleration factor increment must be positive");
    checkArgument(
        parameters.getAccelerationFactorMax() > 0, "Acceleration factor max must be positive");
    checkArgument(
        parameters.getAccelerationFactorMax() >= parameters.getAccelerationFactorStart(),
        "Acceleration factor max must be >= start");
    checkArgument(parameters.getMfiPeriod() > 0, "MFI period must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    ParabolicSarIndicator psar =
        new ParabolicSarIndicator(
            series,
            series.numOf(parameters.getAccelerationFactorStart()),
            series.numOf(parameters.getAccelerationFactorIncrement()),
            series.numOf(parameters.getAccelerationFactorMax()));
    MfiIndicator mfi = new MfiIndicator(series, parameters.getMfiPeriod());

    // Entry: price above SAR (uptrend) and MFI below 20 (oversold)
    Rule entryRule =
        new OverIndicatorRule(closePrice, psar)
            .and(new UnderIndicatorRule(mfi, series.numOf(20)));

    // Exit: price below SAR (downtrend) and MFI above 80 (overbought)
    Rule exitRule =
        new UnderIndicatorRule(closePrice, psar)
            .and(new OverIndicatorRule(mfi, series.numOf(80)));

    return new BaseStrategy(
        String.format(
            "%s (AF: %.3f-%.3f, MFI: %d)",
            "SAR_MFI",
            parameters.getAccelerationFactorStart(),
            parameters.getAccelerationFactorMax(),
            parameters.getMfiPeriod()),
        entryRule,
        exitRule,
        parameters.getMfiPeriod());
  }

  private static class MfiIndicator extends CachedIndicator<Num> {
    private final int timeFrame;
    private final TypicalPriceIndicator typicalPriceIndicator;
    private final BarSeries barSeries;

    MfiIndicator(BarSeries barSeries, int timeFrame) {
      super(barSeries);
      this.barSeries = barSeries;
      this.timeFrame = timeFrame;
      this.typicalPriceIndicator = new TypicalPriceIndicator(barSeries);
    }

    @Override
    protected Num calculate(int index) {
      if (index < timeFrame) {
        return numOf(50);
      }

      Num positiveFlow = numOf(0);
      Num negativeFlow = numOf(0);

      for (int i = index - timeFrame + 1; i <= index; i++) {
        if (i > 0) {
          Num currentTypicalPrice = typicalPriceIndicator.getValue(i);
          Num previousTypicalPrice = typicalPriceIndicator.getValue(i - 1);
          Num volume = barSeries.getBar(i).getVolume();
          Num rawMoneyFlow = currentTypicalPrice.multipliedBy(volume);

          if (currentTypicalPrice.isGreaterThan(previousTypicalPrice)) {
            positiveFlow = positiveFlow.plus(rawMoneyFlow);
          } else if (currentTypicalPrice.isLessThan(previousTypicalPrice)) {
            negativeFlow = negativeFlow.plus(rawMoneyFlow);
          }
        }
      }

      if (negativeFlow.isZero()) {
        return numOf(100);
      }
      if (positiveFlow.isZero()) {
        return numOf(0);
      }

      Num moneyFlowRatio = positiveFlow.dividedBy(negativeFlow);
      return numOf(100).minus(numOf(100).dividedBy(numOf(1).plus(moneyFlowRatio)));
    }

    @Override
    public int getUnstableBars() {
      return timeFrame;
    }
  }
}
