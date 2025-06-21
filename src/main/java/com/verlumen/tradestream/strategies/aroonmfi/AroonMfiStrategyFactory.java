package com.verlumen.tradestream.strategies.aroonmfi;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.AroonMfiParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.TypicalPriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public class AroonMfiStrategyFactory implements StrategyFactory<AroonMfiParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, AroonMfiParameters params) {
    checkArgument(params.getAroonPeriod() > 0, "Aroon period must be positive");
    checkArgument(params.getMfiPeriod() > 0, "MFI period must be positive");
    checkArgument(params.getOverboughtThreshold() > 0, "Overbought threshold must be positive");
    checkArgument(params.getOversoldThreshold() > 0, "Oversold threshold must be positive");
    checkArgument(
        params.getOverboughtThreshold() > params.getOversoldThreshold(),
        "Overbought threshold must be greater than oversold threshold");

    // Custom implementations since they might not be available in ta4j 0.17
    AroonUpIndicator aroonUp = new AroonUpIndicator(series, params.getAroonPeriod());
    AroonDownIndicator aroonDown = new AroonDownIndicator(series, params.getAroonPeriod());
    MFIIndicator mfi = new MFIIndicator(series, params.getMfiPeriod());

    Rule entryRule =
        new CrossedUpIndicatorRule(aroonUp, aroonDown)
            .and(new UnderIndicatorRule(mfi, series.numOf(params.getOversoldThreshold())));

    Rule exitRule =
        new OverIndicatorRule(aroonUp, aroonDown)
            .and(new OverIndicatorRule(mfi, series.numOf(params.getOverboughtThreshold())));

    return new BaseStrategy(
        String.format(
            "%s (Aroon: %d, MFI: %d)",
            StrategyType.AROON_MFI.name(), params.getAroonPeriod(), params.getMfiPeriod()),
        entryRule,
        exitRule,
        Math.max(params.getAroonPeriod(), params.getMfiPeriod()));
  }

  @Override
  public AroonMfiParameters getDefaultParameters() {
    return AroonMfiParameters.newBuilder()
        .setAroonPeriod(25)
        .setMfiPeriod(14)
        .setOverboughtThreshold(80)
        .setOversoldThreshold(20)
        .build();
  }
}

/** Custom Aroon Up indicator implementation */
class AroonUpIndicator extends CachedIndicator<Num> {
  private final int timeFrame;
  private final HighPriceIndicator highPriceIndicator;

  public AroonUpIndicator(BarSeries series, int timeFrame) {
    super(series);
    this.timeFrame = timeFrame;
    this.highPriceIndicator = new HighPriceIndicator(series);
  }

  @Override
  protected Num calculate(int index) {
    if (index < timeFrame - 1) {
      return numOf(0);
    }

    int highestIndex = index - timeFrame + 1;
    Num highestPrice = highPriceIndicator.getValue(highestIndex);

    // Find the index of the highest high within the time frame
    for (int i = index - timeFrame + 2; i <= index; i++) {
      Num currentHigh = highPriceIndicator.getValue(i);
      if (currentHigh.isGreaterThan(highestPrice)) {
        highestPrice = currentHigh;
        highestIndex = i;
      }
    }

    // Calculate periods since highest high
    int periodsSinceHigh = index - highestIndex;
    // Aroon Up = ((timeFrame - periods since highest high) / timeFrame) * 100
    return numOf(timeFrame - periodsSinceHigh).dividedBy(numOf(timeFrame)).multipliedBy(numOf(100));
  }

  @Override
  public int getUnstableBars() {
    return timeFrame;
  }

  @Override
  public String toString() {
    return getClass().getSimpleName() + " timeFrame: " + timeFrame;
  }
}

/** Custom Aroon Down indicator implementation */
class AroonDownIndicator extends CachedIndicator<Num> {
  private final int timeFrame;
  private final LowPriceIndicator lowPriceIndicator;

  public AroonDownIndicator(BarSeries series, int timeFrame) {
    super(series);
    this.timeFrame = timeFrame;
    this.lowPriceIndicator = new LowPriceIndicator(series);
  }

  @Override
  protected Num calculate(int index) {
    if (index < timeFrame - 1) {
      return numOf(0);
    }

    int lowestIndex = index - timeFrame + 1;
    Num lowestPrice = lowPriceIndicator.getValue(lowestIndex);

    // Find the index of the lowest low within the time frame
    for (int i = index - timeFrame + 2; i <= index; i++) {
      Num currentLow = lowPriceIndicator.getValue(i);
      if (currentLow.isLessThan(lowestPrice)) {
        lowestPrice = currentLow;
        lowestIndex = i;
      }
    }

    // Calculate periods since lowest low
    int periodsSinceLow = index - lowestIndex;
    // Aroon Down = ((timeFrame - periods since lowest low) / timeFrame) * 100
    return numOf(timeFrame - periodsSinceLow).dividedBy(numOf(timeFrame)).multipliedBy(numOf(100));
  }

  @Override
  public int getUnstableBars() {
    return timeFrame;
  }

  @Override
  public String toString() {
    return getClass().getSimpleName() + " timeFrame: " + timeFrame;
  }
}

/** Custom Money Flow Index (MFI) indicator implementation */
class MFIIndicator extends CachedIndicator<Num> {
  private final int timeFrame;
  private final TypicalPriceIndicator typicalPriceIndicator;
  private final BarSeries barSeries;

  public MFIIndicator(BarSeries barSeries, int timeFrame) {
    super(barSeries);
    this.barSeries = barSeries;
    this.timeFrame = timeFrame;
    this.typicalPriceIndicator = new TypicalPriceIndicator(barSeries);
  }

  @Override
  protected Num calculate(int index) {
    if (index < timeFrame) {
      return numOf(50); // Default neutral value for insufficient data
    }

    Num positiveFlow = numOf(0);
    Num negativeFlow = numOf(0);

    // Calculate money flow for the specified time frame
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

    // Avoid division by zero
    if (negativeFlow.isZero()) {
      return numOf(100);
    }
    if (positiveFlow.isZero()) {
      return numOf(0);
    }

    // Calculate Money Flow Ratio
    Num moneyFlowRatio = positiveFlow.dividedBy(negativeFlow);

    // Calculate Money Flow Index
    Num mfi = numOf(100).minus(numOf(100).dividedBy(numOf(1).plus(moneyFlowRatio)));

    return mfi;
  }

  @Override
  public int getUnstableBars() {
    return timeFrame;
  }

  @Override
  public String toString() {
    return getClass().getSimpleName() + " timeFrame: " + timeFrame;
  }
}
