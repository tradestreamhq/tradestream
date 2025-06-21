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
import org.ta4j.core.indicators.volume.MFIIndicator;
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
