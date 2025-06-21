package com.verlumen.tradestream.strategies.rsiemacrossover;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.RsiEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.RSIIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.DecimalNum;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class RsiEmaCrossoverStrategyFactory
    implements StrategyFactory<RsiEmaCrossoverParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, RsiEmaCrossoverParameters params) {
    checkArgument(params.getRsiPeriod() > 0, "RSI period must be positive");
    checkArgument(params.getEmaPeriod() > 0, "EMA period must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    RSIIndicator rsi = new RSIIndicator(closePrice, params.getRsiPeriod());
    EMAIndicator rsiEma = new EMAIndicator(rsi, params.getEmaPeriod());

    // Entry rule: RSI crosses above its EMA AND RSI is not overbought (< 70)
    Rule entryRule =
        new CrossedUpIndicatorRule(rsi, rsiEma).and(new UnderIndicatorRule(rsi, DecimalNum.valueOf(70)));

    // Exit rule: RSI crosses below its EMA AND RSI is not oversold (> 30)
    Rule exitRule =
        new CrossedDownIndicatorRule(rsi, rsiEma)
            .and(new OverIndicatorRule(rsi, DecimalNum.valueOf(30)));

    return new BaseStrategy(
        String.format(
            "%s (RSI: %d, EMA: %d)",
            StrategyType.RSI_EMA_CROSSOVER.name(), params.getRsiPeriod(), params.getEmaPeriod()),
        entryRule,
        exitRule,
        Math.max(params.getRsiPeriod(), params.getEmaPeriod()));
  }

  @Override
  public RsiEmaCrossoverParameters getDefaultParameters() {
    return RsiEmaCrossoverParameters.newBuilder()
        .setRsiPeriod(14) // Standard RSI period
        .setEmaPeriod(10) // EMA period for RSI smoothing
        .build();
  }
}
