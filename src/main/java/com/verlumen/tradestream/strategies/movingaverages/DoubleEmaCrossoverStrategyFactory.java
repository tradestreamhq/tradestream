package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

final class DoubleEmaCrossoverStrategyFactory implements StrategyFactory<DoubleEmaCrossoverParameters> {
    static DoubleEmaCrossoverStrategyFactory create() {
        return new DoubleEmaCrossoverStrategyFactory();
    }

    @Override
    public Strategy createStrategy(BarSeries series, DoubleEmaCrossoverParameters params)
            throws InvalidProtocolBufferException {
        checkArgument(params.getShortEmaPeriod() > 0, "Short EMA period must be positive");
        checkArgument(params.getLongEmaPeriod() > 0, "Long EMA period must be positive");
        checkArgument(params.getLongEmaPeriod() > params.getShortEmaPeriod(),
            "Long EMA period must be greater than short EMA period");

        ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
        EMAIndicator shortEma = new EMAIndicator(closePrice, params.getShortEmaPeriod());
        EMAIndicator longEma = new EMAIndicator(closePrice, params.getLongEmaPeriod());

        // Entry rule: Short EMA crosses above Long EMA
        Rule entryRule = new CrossedUpIndicatorRule(shortEma, longEma);

        // Exit rule: Short EMA crosses below Long EMA
        Rule exitRule = new CrossedDownIndicatorRule(shortEma, longEma);

        // Create strategy using the constructor that takes unstable period directly
        return new BaseStrategy(
            String.format("%s (%d, %d)",
                getStrategyType().name(),
                params.getShortEmaPeriod(),
                params.getLongEmaPeriod()),
            entryRule,
            exitRule,
            params.getLongEmaPeriod());
    }

    @Override
    public DoubleEmaCrossoverParameters getDefaultParameters() {
        return DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(12)
            .setLongEmaPeriod(26)
            .build();
    }

    @Override
    public StrategyType getStrategyType() {
        return StrategyType.DOUBLE_EMA_CROSSOVER;
    }

    private DoubleEmaCrossoverStrategyFactory() {}
}
