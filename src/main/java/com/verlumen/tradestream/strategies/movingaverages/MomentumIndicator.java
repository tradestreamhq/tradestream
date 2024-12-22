package com.verlumen.tradestream.strategies.movingaverages;

import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;

final class MomentumIndicator extends CachedIndicator<Num> {
    private final ClosePriceIndicator closePrice;
    private final int period;

    public MomentumIndicator(ClosePriceIndicator closePrice, int period) {
        super(closePrice);
        this.closePrice = closePrice;
        this.period = period;
    }

    @Override
    protected Num calculate(int index) {
        if (index < period) {
            return numOf(0); // Not enough data
        }
        Num currentClose = closePrice.getValue(index);
        Num pastClose = closePrice.getValue(index - period);
        return currentClose.minus(pastClose);
    }
}
