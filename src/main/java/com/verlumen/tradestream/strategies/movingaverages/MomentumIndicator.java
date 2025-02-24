package com.verlumen.tradestream.strategies.movingaverages;

import org.ta4j.core.indicators.CachedIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;

/**
 * Momentum indicator that measures price changes over a specified period as a percentage.
 */
final class MomentumIndicator extends CachedIndicator<Num> {
    private final ClosePriceIndicator closePrice;
    private final int period;

    MomentumIndicator(ClosePriceIndicator closePrice, int period) {
        super(closePrice);
        this.closePrice = closePrice;
        this.period = period;
    }

    @Override
    protected Num calculate(int index) {
        if (index < period) {
            // Not enough data yet
            return numOf(0);
        }
        
        // Calculate percentage change:
        // ((Current Price - Price n periods ago) / Price n periods ago) * 100
        Num currentClose = closePrice.getValue(index);
        Num previousClose = closePrice.getValue(index - period);
        
        return currentClose
            .minus(previousClose)
            .dividedBy(previousClose)
            .multipliedBy(numOf(100));
    }

    @Override
    public int getUnstableBars() {
        return period;
    }
}
