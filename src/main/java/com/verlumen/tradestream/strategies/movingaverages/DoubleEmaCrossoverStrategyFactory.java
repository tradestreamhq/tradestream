package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.inject.Inject;
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

public class DoubleEmaCrossoverStrategyFactory implements StrategyFactory<DoubleEmaCrossoverParameters> {
    @Inject
    DoubleEmaCrossoverStrategyFactory() {}

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

        // Since we need stable EMAs for our calculation, we must wait for enough bars
        // to let both EMAs stabilize. While Ta4j docs suggest setting unstable period
        // to the longest indicator period, for EMAs we actually need more bars due to
        // their exponential nature.
        int unstablePeriod = Math.min(4, params.getLongEmaPeriod() - 1);

        return new BaseStrategy(
            String.format("%s (%d, %d)",
                getStrategyType().name(),
                params.getShortEmaPeriod(), 
                params.getLongEmaPeriod()),
            entryRule,
            exitRule,
            unstablePeriod);
        return strategy;
    }

    @Override
    public StrategyType getStrategyType() {
        return StrategyType.DOUBLE_EMA_CROSSOVER;
    }
}
