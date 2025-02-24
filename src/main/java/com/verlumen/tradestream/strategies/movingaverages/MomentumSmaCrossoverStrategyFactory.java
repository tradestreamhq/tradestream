package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.MomentumSmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.ta4j.core.rules.OverIndicatorRule;
import org.ta4j.core.rules.UnderIndicatorRule;

final class MomentumSmaCrossoverStrategyFactory
    implements StrategyFactory<MomentumSmaCrossoverParameters> {
    static MomentumSmaCrossoverStrategyFactory create() {
        return new MomentumSmaCrossoverStrategyFactory();
    }

    @Override
    public Strategy createStrategy(BarSeries series, MomentumSmaCrossoverParameters params)
        throws InvalidProtocolBufferException {
        checkArgument(params.getMomentumPeriod() > 0, "Momentum period must be positive");
        checkArgument(params.getSmaPeriod() > 0, "SMA period must be positive");
    
        ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
        MomentumIndicator momentumIndicator = new MomentumIndicator(closePrice, params.getMomentumPeriod());
        SMAIndicator smaIndicator = new SMAIndicator(momentumIndicator, params.getSmaPeriod());
    
        // Entry rule - First check if momentum is positive, then check for crossover
        var entryRule = new OverIndicatorRule(momentumIndicator, series.numOf(0))
            .and(new CrossedUpIndicatorRule(momentumIndicator, smaIndicator));
    
        // Exit rule - First check if momentum is negative, then check for crossover
        var exitRule = new UnderIndicatorRule(momentumIndicator, series.numOf(0))
            .and(new CrossedDownIndicatorRule(momentumIndicator, smaIndicator));
    
        String strategyName = String.format(
            "%s (MOM-%d/SMA-%d)",
            getStrategyType().name(),
            params.getMomentumPeriod(),
            params.getSmaPeriod());
    
        return new BaseStrategy(
            strategyName,
            entryRule,
            exitRule,
            Math.max(params.getMomentumPeriod(), params.getSmaPeriod()));
        }

    @Override
    public MomentumSmaCrossoverParameters getDefaultParameters() {
        return MomentumSmaCrossoverParameters.newBuilder()
            .setMomentumPeriod(10)
            .setSmaPeriod(20)
            .build();
    }

    @Override
    public StrategyType getStrategyType() {
        return StrategyType.MOMENTUM_SMA_CROSSOVER;
    }

    private MomentumSmaCrossoverStrategyFactory() {}
}
