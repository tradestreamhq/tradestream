package com.verlumen.tradestream.strategies.aroonmfi;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.AroonMfiParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.AroonDownIndicator;
import org.ta4j.core.indicators.AroonUpIndicator;
import org.ta4j.core.indicators.CachedIndicator;
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

    AroonUpIndicator aroonUp = new AroonUpIndicator(series, params.getAroonPeriod());
    AroonDownIndicator aroonDown = new AroonDownIndicator(series, params.getAroonPeriod());
    
    // Custom MFI implementation since it's not available in ta4j core
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

/**
 * Custom Money Flow Index (MFI) indicator implementation
 * Based on the standard MFI calculation formula
 */
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
  public String toString() {
    return getClass().getSimpleName() + " timeFrame: " + timeFrame;
  }
}
