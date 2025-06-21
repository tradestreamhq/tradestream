package com.verlumen.tradestream.strategies.adxdmi;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.AdxDmiParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.adx.ADXIndicator;
import org.ta4j.core.indicators.adx.MinusDIIndicator;
import org.ta4j.core.indicators.adx.PlusDIIndicator;
import org.ta4j.core.num.DecimalNum;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.ta4j.core.rules.OverIndicatorRule;

public class AdxDmiStrategyFactory implements StrategyFactory<AdxDmiParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, AdxDmiParameters params) {
    checkArgument(params.getAdxPeriod() > 0, "ADX period must be positive");
    checkArgument(params.getDiPeriod() > 0, "DI period must be positive");

    ADXIndicator adx = new ADXIndicator(series, params.getAdxPeriod());
    PlusDIIndicator plusDI = new PlusDIIndicator(series, params.getDiPeriod());
    MinusDIIndicator minusDI = new MinusDIIndicator(series, params.getDiPeriod());

    // Entry rule: ADX is above 25 (strong trend) and +DI crosses above -DI
    Rule entryRule =
        new OverIndicatorRule(adx, DecimalNum.valueOf(25))
            .and(new CrossedUpIndicatorRule(plusDI, minusDI));

    // Exit rule: +DI crosses below -DI
    Rule exitRule = new CrossedDownIndicatorRule(plusDI, minusDI);

    return new BaseStrategy(
        String.format(
            "%s (ADX: %d, DI: %d)",
            StrategyType.ADX_DMI.name(), params.getAdxPeriod(), params.getDiPeriod()),
        entryRule,
        exitRule,
        Math.max(params.getAdxPeriod(), params.getDiPeriod()));
  }

  @Override
  public AdxDmiParameters getDefaultParameters() {
    return AdxDmiParameters.newBuilder()
        .setAdxPeriod(14) // Standard ADX period
        .setDiPeriod(14) // Standard DI period
        .build();
  }
}
