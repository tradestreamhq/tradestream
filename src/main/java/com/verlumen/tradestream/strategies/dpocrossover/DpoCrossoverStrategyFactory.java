package com.verlumen.tradestream.strategies.dpocrossover;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DpoCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.DPOIndicator;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class DpoCrossoverStrategyFactory implements StrategyFactory<DpoCrossoverParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, DpoCrossoverParameters params)
      throws InvalidProtocolBufferException {
    checkArgument(params.getDpoPeriod() > 0, "DPO period must be positive");
    checkArgument(params.getMaPeriod() > 0, "MA period must be positive");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    DPOIndicator dpo = new DPOIndicator(closePrice, params.getDpoPeriod());
    SMAIndicator ma = new SMAIndicator(dpo, params.getMaPeriod());

    Rule entryRule = new CrossedUpIndicatorRule(dpo, ma);
    Rule exitRule = new CrossedDownIndicatorRule(dpo, ma);

    return new BaseStrategy(
        String.format("%s (%d, %d)", "DPO_CROSSOVER", params.getDpoPeriod(), params.getMaPeriod()),
        entryRule,
        exitRule,
        Math.max(params.getDpoPeriod(), params.getMaPeriod()));
  }

  @Override
  public DpoCrossoverParameters getDefaultParameters() {
    return DpoCrossoverParameters.newBuilder().setDpoPeriod(20).setMaPeriod(10).build();
  }
}
