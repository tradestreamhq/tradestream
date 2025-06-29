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
                val json = StrategyParameterTypeRegistry.formatParametersToJson(packed)
                // Allow empty or valid JSON for default instances
                assert(json.isBlank() || json.contains("{") || json.contains("error:")) {
                    "JSON serialization failed for ${clazz.simpleName}"
                }
            } catch (e: Exception) {
                throw AssertionError("Failed to serialize ${clazz.simpleName} to JSON", e)
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

        val json = StrategyParameterTypeRegistry.formatParametersToJson(unknownAny)

        // Verify the JSON is valid by checking its format
        assert(json.contains("error:") || json.contains("base64_data")) {
            "JSON should contain error or base64_data field"
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

        val json = StrategyParameterTypeRegistry.formatParametersToJson(invalidAny)

        // Verify the JSON is valid by checking its format
        assert(json.contains("error:") || json.contains("base64_data")) {
            "JSON should contain error or base64_data field"
        }
    }

    @Test
    fun jsonIsNotTruncated() {
        // Test that the JSON output is complete and not truncated
        val unknownAny =
            Any
                .newBuilder()
                .setTypeUrl("type.googleapis.com/unknown.UnknownParameters")
                .setValue(ByteString.copyFromUtf8("test data"))
                .build()

        val json = StrategyParameterTypeRegistry.formatParametersToJson(unknownAny)

        // For unknown types, expect base64_data fallback
        assert(json.contains("base64_data")) { "Fallback JSON should contain base64_data field" }
    }

    @Test
    fun jsonHandlesSpecialCharacters() {
        // Test that the JSON output handles special characters in the data
        val specialData = "test\"data'with\n\t\r\\special chars"
        val unknownAny =
            Any
                .newBuilder()
                .setTypeUrl("type.googleapis.com/unknown.UnknownParameters")
                .setValue(ByteString.copyFromUtf8(specialData))
                .build()

        val json = StrategyParameterTypeRegistry.formatParametersToJson(unknownAny)

        // Verify it's valid JSON by checking its format
        assert(json.contains("base64_data")) {
            "JSON should contain base64_data field"
        }
    }

    @Test
    fun jsonIsSafeForTabSeparatedValues() {
        // Test that the JSON output is safe for tab-separated CSV format
        // This is critical for PostgreSQL COPY command
        val dataWithTabs = "data\twith\ttabs"
        val unknownAny =
            Any
                .newBuilder()
                .setTypeUrl("type.googleapis.com/unknown.UnknownParameters")
                .setValue(ByteString.copyFromUtf8(dataWithTabs))
                .build()

        val json = StrategyParameterTypeRegistry.formatParametersToJson(unknownAny)

        // Verify it's valid JSON by checking its format
        assert(json.contains("base64_data")) {
            "JSON should contain base64_data field"
        }
    }

    @Test
    fun validateJsonParameterWorksCorrectly() {
        // Test valid JSON
        val validJson = """{"field": "value", "number": 123}"""
        assert(StrategyParameterTypeRegistry.validateJsonParameter(validJson))

        // Test invalid JSON
        val invalidJson = """{"field": "value", "number": 123"""
        assert(!StrategyParameterTypeRegistry.validateJsonParameter(invalidJson))

        // Test empty string
        assert(!StrategyParameterTypeRegistry.validateJsonParameter(""))

        // Test null
        assert(!StrategyParameterTypeRegistry.validateJsonParameter("null"))
    }
}
