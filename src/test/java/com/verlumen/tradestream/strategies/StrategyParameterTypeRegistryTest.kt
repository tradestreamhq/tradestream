package com.verlumen.tradestream.strategies

import com.google.protobuf.Any
import com.google.protobuf.Message
import com.google.protobuf.util.JsonFormat
import org.junit.Test
import kotlin.reflect.full.companionObjectInstance
import kotlin.reflect.full.declaredFunctions
import kotlin.reflect.jvm.isAccessible

class StrategyParameterTypeRegistryTest {
    @Test
    fun allParameterTypesAreSerializableToJson() {
        val registry = StrategyParameterTypeRegistry.registry
        val parameterClasses = listOf(
            SmaRsiParameters::class,
            EmaMacdParameters::class,
            AdxStochasticParameters::class,
            AroonMfiParameters::class,
            IchimokuCloudParameters::class,
            ParabolicSarParameters::class,
            SmaEmaCrossoverParameters::class,
            DoubleEmaCrossoverParameters::class,
            TripleEmaCrossoverParameters::class,
            HeikenAshiParameters::class,
            LinearRegressionChannelsParameters::class,
            VwapMeanReversionParameters::class,
            BbandWRParameters::class,
            AtrCciParameters::class,
            DonchianBreakoutParameters::class,
            VolatilityStopParameters::class,
            AtrTrailingStopParameters::class,
            MomentumSmaCrossoverParameters::class,
            KstOscillatorParameters::class,
            StochasticRsiParameters::class,
            RviParameters::class,
            MassIndexParameters::class,
            MomentumPinballParameters::class,
            VolumeWeightedMacdParameters::class,
            ObvEmaParameters::class,
            ChaikinOscillatorParameters::class,
            KlingerVolumeParameters::class,
            VolumeBreakoutParameters::class,
            PvtParameters::class,
            VptParameters::class,
            VolumeSpreadAnalysisParameters::class,
            TickVolumeAnalysisParameters::class,
            VolumeProfileDeviationsParameters::class,
            VolumeProfileParameters::class,
            StochasticEmaParameters::class,
            CmoMfiParameters::class,
            RsiEmaCrossoverParameters::class,
            TrixSignalLineParameters::class,
            CmfZeroLineParameters::class,
            RainbowOscillatorParameters::class,
            PriceOscillatorSignalParameters::class,
            AwesomeOscillatorParameters::class,
            DemaTemaCrossoverParameters::class,
            ElderRayMAParameters::class,
            FramaParameters::class,
            PivotParameters::class,
            DoubleTopBottomParameters::class,
            FibonacciRetracementsParameters::class,
            PriceGapParameters::class,
            RenkoChartParameters::class,
            RangeBarsParameters::class,
            GannSwingParameters::class,
            SarMfiParameters::class,
            AdxDmiParameters::class,
            DpoCrossoverParameters::class,
            VariablePeriodEmaParameters::class,
            VwapCrossoverParameters::class,
            RocMaCrossoverParameters::class,
            RegressionChannelParameters::class,
            MacdCrossoverParameters::class,
        )
        for (clazz in parameterClasses) {
            // Try to get a default instance
            val defaultInstance = clazz.java.getMethod("getDefaultInstance").invoke(null) as Message
            val packed = Any.pack(defaultInstance)
            try {
                val json = JsonFormat.printer().usingTypeRegistry(registry).print(packed)
                assert(json != "{}") { "JSON serialization failed for ${clazz.simpleName}" }
            } catch (e: Exception) {
                throw AssertionError("Failed to serialize ${clazz.simpleName} to JSON", e)
            }
        }
    }
} 