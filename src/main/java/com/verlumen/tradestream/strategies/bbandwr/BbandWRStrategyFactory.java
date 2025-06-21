package com.verlumen.tradestream.strategies.bbandwr;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.BbandWRParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.averages.SMAIndicator;
import org.ta4j.core.indicators.WilliamsRIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsLowerIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsMiddleIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsUpperIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.statistics.StandardDeviationIndicator;
import org.ta4j.core.num.DecimalNum;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class BbandWRStrategyFactory implements StrategyFactory<BbandWRParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, BbandWRParameters params) {
    checkArgument(params.getBbandsPeriod() > 0, "Bollinger Bands period must be positive");
    checkArgument(params.getWrPeriod() > 0, "Williams %R period must be positive");
    checkArgument(
        params.getStdDevMultiplier() > 0, "Standard deviation multiplier must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    // Bollinger Bands
    SMAIndicator sma = new SMAIndicator(closePrice, params.getBbandsPeriod());
    BollingerBandsMiddleIndicator bbMiddle = new BollingerBandsMiddleIndicator(sma);
    StandardDeviationIndicator stdDev =
        new StandardDeviationIndicator(closePrice, params.getBbandsPeriod());
    BollingerBandsUpperIndicator bbUpper =
        new BollingerBandsUpperIndicator(
            bbMiddle, stdDev, DecimalNum.valueOf(params.getStdDevMultiplier()));
    BollingerBandsLowerIndicator bbLower =
        new BollingerBandsLowerIndicator(
            bbMiddle, stdDev, DecimalNum.valueOf(params.getStdDevMultiplier()));

    // Williams %R
    WilliamsRIndicator williamsR = new WilliamsRIndicator(series, params.getWrPeriod());

    // Entry rule: Price touches/crosses below lower Bollinger Band AND Williams %R is oversold (<
    // -80)
    Rule entryRule =
        new UnderIndicatorRule(closePrice, bbLower)
            .and(new UnderIndicatorRule(williamsR, DecimalNum.valueOf(-80)));

    // Exit rule: Price touches/crosses above upper Bollinger Band AND Williams %R is overbought (>
    // -20)
    Rule exitRule =
        new OverIndicatorRule(closePrice, bbUpper)
            .and(new OverIndicatorRule(williamsR, DecimalNum.valueOf(-20)));

    return new BaseStrategy(
        String.format(
            "%s (BB: %d, WR: %d, StdDev: %.1f)",
            StrategyType.BBAND_W_R.name(),
            params.getBbandsPeriod(),
            params.getWrPeriod(),
            params.getStdDevMultiplier()),
        entryRule,
        exitRule,
        Math.max(params.getBbandsPeriod(), params.getWrPeriod()));
  }

  @Override
  public BbandWRParameters getDefaultParameters() {
    return BbandWRParameters.newBuilder()
        .setBbandsPeriod(20) // Standard Bollinger Bands period
        .setWrPeriod(14) // Standard Williams %R period
        .setStdDevMultiplier(2.0) // Standard deviation multiplier
        .build();
  }
}
