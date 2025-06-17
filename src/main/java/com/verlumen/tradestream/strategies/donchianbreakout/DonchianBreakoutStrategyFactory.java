package com.verlumen.tradestream.strategies.donchianbreakout;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.DonchianBreakoutParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.HighestValueIndicator;
import org.ta4j.core.indicators.LowestValueIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class DonchianBreakoutStrategyFactory implements StrategyFactory<DonchianBreakoutParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, DonchianBreakoutParameters params) {
    checkArgument(params.getDonchianPeriod() > 0, "Donchian period must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    
    // Donchian Channel Upper = Highest High over the period
    HighPriceIndicator highPrice = new HighPriceIndicator(series);
    HighestValueIndicator upperChannel = new HighestValueIndicator(highPrice, params.getDonchianPeriod());
    
    // Donchian Channel Lower = Lowest Low over the period
    LowPriceIndicator lowPrice = new LowPriceIndicator(series);
    LowestValueIndicator lowerChannel = new LowestValueIndicator(lowPrice, params.getDonchianPeriod());

    // Entry rule: Buy when price crosses above upper Donchian channel
    Rule entryRule = new OverIndicatorRule(closePrice, upperChannel);

    // Exit rule: Sell when price crosses below lower Donchian channel
    Rule exitRule = new UnderIndicatorRule(closePrice, lowerChannel);

    return new BaseStrategy(
        String.format("%s (Period: %d)", getStrategyType().name(), params.getDonchianPeriod()),
        entryRule,
        exitRule,
        params.getDonchianPeriod());
  }

  @Override
  public DonchianBreakoutParameters getDefaultParameters() {
    return DonchianBreakoutParameters.newBuilder()
        .setDonchianPeriod(20)  // Common Donchian channel period
        .build();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.DONCHIAN_BREAKOUT;
  }
}
