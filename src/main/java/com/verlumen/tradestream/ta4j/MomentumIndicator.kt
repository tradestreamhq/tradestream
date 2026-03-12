package com.verlumen.tradestream.ta4j

import org.ta4j.core.indicators.CachedIndicator
import org.ta4j.core.indicators.helpers.ClosePriceIndicator
import org.ta4j.core.num.Num

/** Momentum indicator that measures price changes over a specified period as a percentage. */
class MomentumIndicator(
    private val closePrice: ClosePriceIndicator,
    private val period: Int,
) : CachedIndicator<Num>(closePrice) {
    override fun calculate(index: Int): Num =
        if (index < period) {
            barSeries.numFactory().zero() // Not enough data yet
        } else {
            // ((Current Price - Price n periods ago) / Price n periods ago) * 100
            val currentClose = closePrice.getValue(index)
            val previousClose = closePrice.getValue(index - period)
            currentClose.minus(previousClose).dividedBy(previousClose).multipliedBy(barSeries.numFactory().hundred())
        }

    override fun getCountOfUnstableBars(): Int = period
}
