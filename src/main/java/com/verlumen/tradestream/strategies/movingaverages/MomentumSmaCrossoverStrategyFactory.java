package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.MomentumSmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.ConstantIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

public class MomentumSmaCrossoverStrategyFactory 
    implements StrategyFactory<MomentumSmaCrossoverParameters> {

    @Inject
    MomentumSmaCrossoverStrategyFactory() {}

    @Override
    public Strategy createStrategy(BarSeries series, MomentumSmaCrossoverParameters params)
        throws InvalidProtocolBufferException {
        checkArgument(params.getMomentumPeriod() > 0, "Momentum period must be positive");
        checkArgument(params.getSmaPeriod() > 0, "SMA period must be positive");

        ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
        
        // Create momentum indicator using percentage change
        MomentumIndicator momentumIndicator = new MomentumIndicator(closePrice, params.getMomentumPeriod());
        
        // Create SMA of the momentum values 
        SMAIndicator smaIndicator = new SMAIndicator(momentumIndicator, params.getSmaPeriod());
        
        // Create zero line indicator for crossover reference
        ConstantIndicator<Num> zeroLine = new ConstantIndicator<>(series, series.numOf(0));

        // Entry rule - SMA crosses above zero line (indicating sustained upward momentum)
        var entryRule = new CrossedUpIndicatorRule(smaIndicator, zeroLine);

        // Exit rule - SMA crosses below zero line (indicating sustained downward momentum)
        var exitRule = new CrossedDownIndicatorRule(smaIndicator, zeroLine);

        String strategyName = String.format(
            "%s (MOM-%d/SMA-%d)", 
            getStrategyType().name(), 
            params.getMomentumPeriod(), 
            params.getSmaPeriod()
        );

        return new BaseStrategy(
            strategyName,
            entryRule,
            exitRule,
            Math.max(params.getMomentumPeriod(), params.getSmaPeriod())
        );
    }

    @Override
    public StrategyType getStrategyType() {
        return StrategyType.MOMENTUM_SMA_CROSSOVER;
    }
}
