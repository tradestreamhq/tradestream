package com.verlumen.tradestream.strategies.doubletopbottom;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DoubleTopBottomParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public final class DoubleTopBottomStrategyFactory
    implements StrategyFactory<DoubleTopBottomParameters> {

  @Override
  public DoubleTopBottomParameters getDefaultParameters() {
    return DoubleTopBottomParameters.newBuilder().setPeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, DoubleTopBottomParameters parameters) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator ema = new EMAIndicator(closePrice, parameters.getPeriod());

    // Entry: Buy when price crosses above EMA (potential double bottom)
    // Exit: Sell when price crosses below EMA (potential double top)
    return new org.ta4j.core.BaseStrategy(
        new CrossedUpIndicatorRule(closePrice, ema), new CrossedDownIndicatorRule(closePrice, ema));
  }

  @Override
  public Strategy createStrategy(BarSeries series, Any parameters)
      throws InvalidProtocolBufferException {
    DoubleTopBottomParameters unpackedParameters =
        parameters.unpack(DoubleTopBottomParameters.class);
    return createStrategy(series, unpackedParameters);
  }
}
