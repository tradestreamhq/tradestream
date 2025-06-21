package com.verlumen.tradestream.strategies.parabolicsarr;

import static com.google.common.base.Preconditions.checkArgument;

import com.verlumen.tradestream.strategies.ParabolicSarParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.ParabolicSarIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

public final class ParabolicSarStrategyFactory implements StrategyFactory<ParabolicSarParameters> {
  @Override
  public Strategy createStrategy(BarSeries series, ParabolicSarParameters params) {
    checkArgument(
        params.getAccelerationFactorStart() > 0, "Acceleration factor start must be positive");
    checkArgument(
        params.getAccelerationFactorIncrement() > 0,
        "Acceleration factor increment must be positive");
    checkArgument(
        params.getAccelerationFactorMax() > 0, "Acceleration factor max must be positive");
    checkArgument(
        params.getAccelerationFactorMax() >= params.getAccelerationFactorStart(),
        "Acceleration factor max must be >= start");

    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    ParabolicSarIndicator psar =
        new ParabolicSarIndicator(
            series,
            series.numOf(params.getAccelerationFactorStart()),
            series.numOf(params.getAccelerationFactorIncrement()),
            series.numOf(params.getAccelerationFactorMax()));

    // Entry rule: Buy when price crosses above Parabolic SAR
    Rule entryRule = new OverIndicatorRule(closePrice, psar);

    // Exit rule: Sell when price crosses below Parabolic SAR
    Rule exitRule = new UnderIndicatorRule(closePrice, psar);

    return new BaseStrategy(
        String.format(
            "%s (AF: %.3f-%.3f, Inc: %.3f)",
            getStrategyType().name(),
            params.getAccelerationFactorStart(),
            params.getAccelerationFactorMax(),
            params.getAccelerationFactorIncrement()),
        entryRule,
        exitRule,
        1); // Minimal unstable period for PSAR
  }

  @Override
  public ParabolicSarParameters getDefaultParameters() {
    return ParabolicSarParameters.newBuilder()
        .setAccelerationFactorStart(0.02) // Standard PSAR start
        .setAccelerationFactorIncrement(0.02) // Standard increment
        .setAccelerationFactorMax(0.2) // Standard max
        .build();
  }

}
