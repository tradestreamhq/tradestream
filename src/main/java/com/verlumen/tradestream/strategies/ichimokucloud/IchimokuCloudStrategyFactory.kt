package com.verlumen.tradestream.strategies.ichimokucloud

import com.google.common.base.Preconditions.checkArgument
import com.verlumen.tradestream.strategies.IchimokuCloudParameters
import com.verlumen.tradestream.strategies.StrategyFactory
import com.verlumen.tradestream.strategies.StrategyType
import org.ta4j.core.BarSeries
import org.ta4j.core.BaseStrategy
import org.ta4j.core.Strategy
import org.ta4j.core.indicators.CachedIndicator
import org.ta4j.core.indicators.helpers.ClosePriceIndicator
import org.ta4j.core.indicators.helpers.HighPriceIndicator
import org.ta4j.core.indicators.helpers.HighestValueIndicator
import org.ta4j.core.indicators.helpers.LowPriceIndicator
import org.ta4j.core.indicators.helpers.LowestValueIndicator
import org.ta4j.core.num.Num
import org.ta4j.core.rules.OverIndicatorRule
import org.ta4j.core.rules.UnderIndicatorRule

class IchimokuCloudStrategyFactory : StrategyFactory<IchimokuCloudParameters> {
    override fun createStrategy(
        series: BarSeries,
        params: IchimokuCloudParameters,
    ): Strategy {
        checkArgument(params.tenkanSenPeriod > 0, "Tenkan-sen period must be positive")
        checkArgument(params.kijunSenPeriod > 0, "Kijun-sen period must be positive")
        checkArgument(params.senkouSpanBPeriod > 0, "Senkou Span B period must be positive")
        checkArgument(params.chikouSpanPeriod > 0, "Chikou Span period must be positive")

        val closePrice = ClosePriceIndicator(series)
        val highPrice = HighPriceIndicator(series)
        val lowPrice = LowPriceIndicator(series)

        // Tenkan-sen (Conversion Line): (highest high + lowest low) / 2 over Tenkan period
        val tenkanSen = IchimokuLineIndicator(highPrice, lowPrice, params.tenkanSenPeriod)

        // Kijun-sen (Base Line): (highest high + lowest low) / 2 over Kijun period
        val kijunSen = IchimokuLineIndicator(highPrice, lowPrice, params.kijunSenPeriod)

        // Senkou Span A (Leading Span A): (Tenkan-sen + Kijun-sen) / 2, plotted 26 periods ahead
        val senkouSpanA = SenkouSpanAIndicator(tenkanSen, kijunSen)

        // Senkou Span B (Leading Span B): (highest high + lowest low) / 2 over Senkou Span B period, plotted 26 periods ahead
        val senkouSpanB = IchimokuLineIndicator(highPrice, lowPrice, params.senkouSpanBPeriod)

        // Chikou Span (Lagging Span): Current close price plotted 26 periods behind
        val chikouSpan = ChikouSpanIndicator(closePrice, params.chikouSpanPeriod)

        // Entry rule:
        // - Price is above the cloud (above both Senkou Span A and B)
        // - Tenkan-sen is above Kijun-sen
        // - Chikou Span is above the price from 26 periods ago
        val entryRule =
            OverIndicatorRule(closePrice, senkouSpanA)
                .and(OverIndicatorRule(closePrice, senkouSpanB))
                .and(OverIndicatorRule(tenkanSen, kijunSen))
                .and(OverIndicatorRule(chikouSpan, closePrice))

        // Exit rule:
        // - Price falls below the cloud (below both Senkou Span A and B)
        // - Tenkan-sen falls below Kijun-sen
        val exitRule =
            UnderIndicatorRule(closePrice, senkouSpanA)
                .or(UnderIndicatorRule(closePrice, senkouSpanB))
                .or(UnderIndicatorRule(tenkanSen, kijunSen))

        return BaseStrategy(
            String.format(
                "%s (Tenkan: %d, Kijun: %d, Senkou B: %d, Chikou: %d)",
                StrategyType.ICHIMOKU_CLOUD.name,
                params.tenkanSenPeriod,
                params.kijunSenPeriod,
                params.senkouSpanBPeriod,
                params.chikouSpanPeriod,
            ),
            entryRule,
            exitRule,
            maxOf(params.tenkanSenPeriod, params.kijunSenPeriod, params.senkouSpanBPeriod, params.chikouSpanPeriod),
        )
    }

    override fun getDefaultParameters(): IchimokuCloudParameters =
        IchimokuCloudParameters
            .newBuilder()
            .setTenkanSenPeriod(9) // Standard Tenkan-sen period
            .setKijunSenPeriod(26) // Standard Kijun-sen period
            .setSenkouSpanBPeriod(52) // Standard Senkou Span B period
            .setChikouSpanPeriod(26) // Standard Chikou Span period
            .build()
}

// Custom indicator for Ichimoku lines (Tenkan-sen, Kijun-sen, Senkou Span B)
private class IchimokuLineIndicator(
    private val highPrice: HighPriceIndicator,
    private val lowPrice: LowPriceIndicator,
    private val period: Int,
) : CachedIndicator<Num>(highPrice) {
    override fun calculate(index: Int): Num {
        if (index < period - 1) {
            return numOf(0)
        }

        val highestHigh = HighestValueIndicator(highPrice, period).getValue(index)
        val lowestLow = LowestValueIndicator(lowPrice, period).getValue(index)

        return highestHigh.plus(lowestLow).dividedBy(numOf(2))
    }

    override fun getUnstableBars(): Int = period
}

// Senkou Span A indicator
private class SenkouSpanAIndicator(
    private val tenkanSen: IchimokuLineIndicator,
    private val kijunSen: IchimokuLineIndicator,
) : CachedIndicator<Num>(tenkanSen) {
    override fun calculate(index: Int): Num {
        val tenkanValue = tenkanSen.getValue(index)
        val kijunValue = kijunSen.getValue(index)
        return tenkanValue.plus(kijunValue).dividedBy(numOf(2))
    }

    override fun getUnstableBars(): Int = maxOf(tenkanSen.unstableBars, kijunSen.unstableBars)
}

// Chikou Span indicator
private class ChikouSpanIndicator(
    private val closePrice: ClosePriceIndicator,
    private val period: Int,
) : CachedIndicator<Num>(closePrice) {
    override fun calculate(index: Int): Num {
        // Chikou Span is the current close price, but we compare it to price from periods ago
        return closePrice.getValue(index)
    }

    override fun getUnstableBars(): Int = period
}
