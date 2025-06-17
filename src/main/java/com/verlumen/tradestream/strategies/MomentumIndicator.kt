package com.verlumen.tradestream.strategies

import org.ta4j.core.indicators.CachedIndicator
import org.ta4j.core.indicators.helpers.ClosePriceIndicator
import org.ta4j.core.num.Num

/** Momentum indicator that measures price changes over a specified period as a percentage. */
class MomentumIndicator(
    private val closePrice: ClosePriceIndicator,
    private val period: Int
) : CachedIndicator<Num>(closePrice) {

    override fun calculate(index: Int): Num {
        if (index < period) {
            // Not enough data yet
            return numOf(0)
        }
        // Calculate percentage change:
        // ((Current Price - Price n periods ago) / Price n periods ago) * 100
        val currentClose = closePrice.getValue(index)
        val previousClose = closePrice.getValue(index - period)
        return currentClose.minus(previousClose).dividedBy(previousClose).multipliedBy(numOf(100))
    }

    override fun getUnstableBars(): Int = period
}
