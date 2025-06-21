package com.verlumen.tradestream.strategies.atrcci;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.AtrCciParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.ATRIndicator;
import org.ta4j.core.indicators.CCIIndicator;
import org.ta4j.core.indicators.helpers.PreviousValueIndicator;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class AtrCciStrategyFactory implements StrategyFactory<AtrCciParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, AtrCciParameters params) {
    checkArgument(params.getAtrPeriod() > 0, "ATR period must be positive");
    checkArgument(params.getCciPeriod() > 0, "CCI period must be positive");

    ATRIndicator atr = new ATRIndicator(series, params.getAtrPeriod());
    CCIIndicator cci = new CCIIndicator(series, params.getCciPeriod());
    PreviousValueIndicator previousAtr = new PreviousValueIndicator(atr, 1);

    // Entry rule: CCI crosses above -100 AND ATR is increasing (indicating rising volatility)
    Rule entryRule =
        new OverIndicatorRule(cci, series.numOf(-100)).and(new OverIndicatorRule(atr, previousAtr));

    // Exit rule: CCI crosses below +100 AND ATR is decreasing (indicating falling volatility)
    Rule exitRule =
        new UnderIndicatorRule(cci, series.numOf(100))
            .and(new UnderIndicatorRule(atr, previousAtr));

    return new BaseStrategy(
        String.format(
            "%s (ATR: %d, CCI: %d)",
            getStrategyType().name(), params.getAtrPeriod(), params.getCciPeriod()),
        entryRule,
        exitRule,
        Math.max(params.getAtrPeriod(), params.getCciPeriod()));
  }

  @Override
  public AtrCciParameters getDefaultParameters() {
    return AtrCciParameters.newBuilder()
        .setAtrPeriod(14) // Standard ATR period
        .setCciPeriod(20) // Standard CCI period
        .build();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.ATR_CCI;
  }
}
