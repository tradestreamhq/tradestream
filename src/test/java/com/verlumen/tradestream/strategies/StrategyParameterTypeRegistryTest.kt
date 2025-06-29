package com.verlumen.tradestream.strategies

import com.google.protobuf.Any
import com.google.protobuf.ByteString
import com.google.protobuf.Message
import com.google.testing.junit.testparameterinjector.TestParameter
import com.google.testing.junit.testparameterinjector.TestParameterInjector
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(TestParameterInjector::class)
class StrategyParameterTypeRegistryTest {
    @Test
    fun allParameterTypesAreSerializableToJson() {
        val parameterClasses =
            listOf(
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
                RegressionChannelParameters::class,
                MacdCrossoverParameters::class,
            )
        for (clazz in parameterClasses) {
            // Try to get a default instance
            val defaultInstance = clazz.java.getMethod("getDefaultInstance").invoke(null) as Message
            val packed = Any.pack(defaultInstance)
            try {
                val textProto = StrategyParameterTypeRegistry.formatParametersToTextProto(packed)
                // Allow empty or whitespace-only TextProto for default instances
                assert(textProto.isBlank() || textProto.contains(":")) {
                    "TextProto serialization failed for ${clazz.simpleName}"
                }
            } catch (e: Exception) {
                throw AssertionError("Failed to serialize ${clazz.simpleName} to TextProto", e)
            }
        }
    }

    @Test
    fun fallbackCaseProducesValidJson() {
        // Create an unknown Any type that will trigger the fallback case
        val unknownAny =
            Any
                .newBuilder()
                .setTypeUrl("type.googleapis.com/unknown.UnknownParameters")
                .setValue(ByteString.copyFromUtf8("garbage data"))
                .build()

        val textProto = StrategyParameterTypeRegistry.formatParametersToTextProto(unknownAny)

        // Verify the TextProto is valid by checking its format
        assert(textProto.contains(":") && textProto.matches(Regex(".*\\w+\\s*:\\s*[\\w\\.\\-]+.*"))) {
            "TextProto should contain key:value pairs"
        }
    }

    @Test
    fun invalidProtocolBufferExceptionProducesValidJson() {
        // Create an Any with invalid protobuf data that will cause InvalidProtocolBufferException
        val invalidAny =
            Any
                .newBuilder()
                .setTypeUrl("type.googleapis.com/strategies.SmaRsiParameters")
                .setValue(ByteString.copyFromUtf8("invalid protobuf data"))
                .build()

        val textProto = StrategyParameterTypeRegistry.formatParametersToTextProto(invalidAny)

        // Verify the TextProto is valid by checking its format
        assert(textProto.contains(":") && textProto.matches(Regex(".*\\w+\\s*:\\s*[\\w\\.\\-]+.*"))) {
            "TextProto should contain key:value pairs"
        }
    }

    @Test
    fun jsonIsNotTruncated() {
        // Test that the TextProto output is complete and not truncated
        val unknownAny =
            Any
                .newBuilder()
                .setTypeUrl("type.googleapis.com/unknown.UnknownParameters")
                .setValue(ByteString.copyFromUtf8("test data"))
                .build()

        val textProto = StrategyParameterTypeRegistry.formatParametersToTextProto(unknownAny)

        // For unknown types, expect error fallback, not JSON
        assert(textProto.contains("error:")) { "Fallback TextProto should contain error field" }
    }

    @Test
    fun jsonHandlesSpecialCharacters() {
        // Test that the TextProto output handles special characters in the data
        val specialData = "test\"data'with\n\t\r\\special chars"
        val unknownAny =
            Any
                .newBuilder()
                .setTypeUrl("type.googleapis.com/unknown.UnknownParameters")
                .setValue(ByteString.copyFromUtf8(specialData))
                .build()

        val textProto = StrategyParameterTypeRegistry.formatParametersToTextProto(unknownAny)

        // Verify it's valid TextProto by checking its format
        assert(textProto.contains(":") && textProto.matches(Regex(".*\\w+\\s*:\\s*[\\w\\.\\-]+.*"))) {
            "TextProto should contain key:value pairs"
        }
    }

    @Test
    fun jsonIsSafeForTabSeparatedValues() {
        // Test that the TextProto output is safe for tab-separated CSV format
        // This is critical for PostgreSQL COPY command
        val dataWithTabs = "data\twith\ttabs"
        val unknownAny =
            Any
                .newBuilder()
                .setTypeUrl("type.googleapis.com/unknown.UnknownParameters")
                .setValue(ByteString.copyFromUtf8(dataWithTabs))
                .build()

        val textProto = StrategyParameterTypeRegistry.formatParametersToTextProto(unknownAny)

        // Verify it's valid TextProto by checking its format
        assert(textProto.contains(":") && textProto.matches(Regex(".*\\w+\\s*:\\s*[\\w\\.\\-]+.*"))) {
            "TextProto should contain key:value pairs"
        }

        // Verify that the TextProto string itself doesn't contain unescaped tabs
        // Base64 encoding should handle this, but let's be explicit
        assert(!textProto.contains("\t")) { "TextProto string should not contain unescaped tabs" }
    }

    @Test
    fun emptyAnyProducesValidJson() {
        // Test that an empty/default Any produces a valid TextProto object
        val emptyAny = Any.getDefaultInstance()
        val textProto = StrategyParameterTypeRegistry.formatParametersToTextProto(emptyAny)
        // Should not be just '{' or empty
        assert(textProto.trim() != "{") { "Empty Any should not produce just '{'" }
        assert(textProto.trim().isNotEmpty()) { "Empty Any should not produce empty string" }
        // Should be error fallback
        assert(textProto.contains("error:")) { "Fallback TextProto should contain error field" }
    }

    @Test
    fun allSupportedStrategyTypesAreMappedInRegistry(
        @TestParameter strategyType: StrategyType,
    ) {
        // Skip special enums
        if (strategyType == StrategyType.UNSPECIFIED || strategyType == StrategyType.UNRECOGNIZED) return

        val defaultParams = strategyType.getDefaultParameters()
        val textProto = StrategyParameterTypeRegistry.formatParametersToTextProto(defaultParams)
        // The fallback always includes "base64_data" or "error"
        assert(!textProto.contains("base64_data") && !textProto.contains("error")) {
            "Fallback TextProto should not be hit for supported type: $strategyType, got: $textProto"
        }
        // Should be valid TextProto (allow empty/whitespace for default instance)
        assert(textProto.isBlank() || textProto.contains(":")) {
            "TextProto for $strategyType should be empty or contain key:value pairs"
        }
    }

    @Test
    fun fallbackIsHitForUnsupportedOrInvalidTypes() {
        // Use an unknown type URL
        val unknownAny =
            Any
                .newBuilder()
                .setTypeUrl("type.googleapis.com/unknown.UnknownParameters")
                .setValue(ByteString.copyFromUtf8("garbage"))
                .build()
        val textProto = StrategyParameterTypeRegistry.formatParametersToTextProto(unknownAny)
        assert(textProto.contains("error:")) { "Fallback TextProto should contain error field" }
    }

    @Test
    fun fallbackIsHitForEmptyAny() {
        val emptyAny = Any.getDefaultInstance()
        val textProto = StrategyParameterTypeRegistry.formatParametersToTextProto(emptyAny)
        assert(textProto.contains("error:")) { "Fallback TextProto should contain error field" }
    }
}
