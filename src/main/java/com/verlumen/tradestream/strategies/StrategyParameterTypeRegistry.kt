package com.verlumen.tradestream.strategies

import com.google.common.flogger.FluentLogger
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.google.protobuf.Any
import com.google.protobuf.InvalidProtocolBufferException
import com.google.protobuf.TextFormat
import com.verlumen.tradestream.strategies.AdxDmiParameters
import com.verlumen.tradestream.strategies.AdxStochasticParameters
import com.verlumen.tradestream.strategies.AroonMfiParameters
import com.verlumen.tradestream.strategies.AtrCciParameters
import com.verlumen.tradestream.strategies.AtrTrailingStopParameters
import com.verlumen.tradestream.strategies.AwesomeOscillatorParameters
import com.verlumen.tradestream.strategies.BbandWRParameters
import com.verlumen.tradestream.strategies.ChaikinOscillatorParameters
import com.verlumen.tradestream.strategies.CmfZeroLineParameters
import com.verlumen.tradestream.strategies.CmoMfiParameters
import com.verlumen.tradestream.strategies.DemaTemaCrossoverParameters
import com.verlumen.tradestream.strategies.DonchianBreakoutParameters
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters
import com.verlumen.tradestream.strategies.DoubleTopBottomParameters
import com.verlumen.tradestream.strategies.DpoCrossoverParameters
import com.verlumen.tradestream.strategies.ElderRayMAParameters
import com.verlumen.tradestream.strategies.EmaMacdParameters
import com.verlumen.tradestream.strategies.FibonacciRetracementsParameters
import com.verlumen.tradestream.strategies.FramaParameters
import com.verlumen.tradestream.strategies.GannSwingParameters
import com.verlumen.tradestream.strategies.HeikenAshiParameters
import com.verlumen.tradestream.strategies.IchimokuCloudParameters
import com.verlumen.tradestream.strategies.KlingerVolumeParameters
import com.verlumen.tradestream.strategies.KstOscillatorParameters
import com.verlumen.tradestream.strategies.LinearRegressionChannelsParameters
import com.verlumen.tradestream.strategies.MacdCrossoverParameters
import com.verlumen.tradestream.strategies.MassIndexParameters
import com.verlumen.tradestream.strategies.MomentumPinballParameters
import com.verlumen.tradestream.strategies.MomentumSmaCrossoverParameters
import com.verlumen.tradestream.strategies.ObvEmaParameters
import com.verlumen.tradestream.strategies.ParabolicSarParameters
import com.verlumen.tradestream.strategies.PivotParameters
import com.verlumen.tradestream.strategies.PriceGapParameters
import com.verlumen.tradestream.strategies.PriceOscillatorSignalParameters
import com.verlumen.tradestream.strategies.PvtParameters
import com.verlumen.tradestream.strategies.RainbowOscillatorParameters
import com.verlumen.tradestream.strategies.RangeBarsParameters
import com.verlumen.tradestream.strategies.RegressionChannelParameters
import com.verlumen.tradestream.strategies.RenkoChartParameters
import com.verlumen.tradestream.strategies.RocMaCrossoverParameters
import com.verlumen.tradestream.strategies.RsiEmaCrossoverParameters
import com.verlumen.tradestream.strategies.RviParameters
import com.verlumen.tradestream.strategies.SarMfiParameters
import com.verlumen.tradestream.strategies.SmaEmaCrossoverParameters
import com.verlumen.tradestream.strategies.SmaRsiParameters
import com.verlumen.tradestream.strategies.StochasticEmaParameters
import com.verlumen.tradestream.strategies.StochasticRsiParameters
import com.verlumen.tradestream.strategies.TickVolumeAnalysisParameters
import com.verlumen.tradestream.strategies.TripleEmaCrossoverParameters
import com.verlumen.tradestream.strategies.TrixSignalLineParameters
import com.verlumen.tradestream.strategies.VariablePeriodEmaParameters
import com.verlumen.tradestream.strategies.VolatilityStopParameters
import com.verlumen.tradestream.strategies.VolumeBreakoutParameters
import com.verlumen.tradestream.strategies.VolumeProfileDeviationsParameters
import com.verlumen.tradestream.strategies.VolumeProfileParameters
import com.verlumen.tradestream.strategies.VolumeSpreadAnalysisParameters
import com.verlumen.tradestream.strategies.VolumeWeightedMacdParameters
import com.verlumen.tradestream.strategies.VptParameters
import com.verlumen.tradestream.strategies.VwapCrossoverParameters
import com.verlumen.tradestream.strategies.VwapMeanReversionParameters

object StrategyParameterTypeRegistry {
    // Trigger new build with JSON serialization fix
    private val logger = FluentLogger.forEnclosingClass()

    fun formatParametersToTextProto(any: Any): String =
        try {
            if (any.typeUrl.isNullOrBlank() || any.value == com.google.protobuf.ByteString.EMPTY) {
                createErrorJson("empty parameters")
            } else {
                val textProtoString =
                    when (any.typeUrl) {
                        "type.googleapis.com/strategies.SmaRsiParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(SmaRsiParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.EmaMacdParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(EmaMacdParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.AdxStochasticParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(AdxStochasticParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.AroonMfiParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(AroonMfiParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.IchimokuCloudParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(IchimokuCloudParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.ParabolicSarParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(ParabolicSarParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.SmaEmaCrossoverParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(SmaEmaCrossoverParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.DoubleEmaCrossoverParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(DoubleEmaCrossoverParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.TripleEmaCrossoverParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(TripleEmaCrossoverParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.MacdCrossoverParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(MacdCrossoverParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.RsiEmaCrossoverParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(RsiEmaCrossoverParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.StochasticEmaParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(StochasticEmaParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.StochasticRsiParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(StochasticRsiParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.VwapCrossoverParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(VwapCrossoverParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.VwapMeanReversionParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(VwapMeanReversionParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.VolumeWeightedMacdParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(VolumeWeightedMacdParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.ObvEmaParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(ObvEmaParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.PvtParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(PvtParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.VptParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(VptParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.VolumeBreakoutParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(VolumeBreakoutParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.VolumeSpreadAnalysisParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(VolumeSpreadAnalysisParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.TrixSignalLineParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(TrixSignalLineParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.DemaTemaCrossoverParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(DemaTemaCrossoverParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.AwesomeOscillatorParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(AwesomeOscillatorParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.RainbowOscillatorParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(RainbowOscillatorParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.RegressionChannelParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(RegressionChannelParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.PriceOscillatorSignalParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(PriceOscillatorSignalParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.RenkoChartParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(RenkoChartParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.RangeBarsParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(RangeBarsParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.GannSwingParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(GannSwingParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.SarMfiParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(SarMfiParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.DpoCrossoverParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(DpoCrossoverParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.VariablePeriodEmaParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(VariablePeriodEmaParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.VolumeProfileParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(VolumeProfileParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.VolumeProfileDeviationsParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(VolumeProfileDeviationsParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.AdxDmiParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(AdxDmiParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.AtrCciParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(AtrCciParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.AtrTrailingStopParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(AtrTrailingStopParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.BbandWRParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(BbandWRParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.ChaikinOscillatorParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(ChaikinOscillatorParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.CmfZeroLineParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(CmfZeroLineParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.DonchianBreakoutParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(DonchianBreakoutParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.DoubleTopBottomParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(DoubleTopBottomParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.FibonacciRetracementsParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(FibonacciRetracementsParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.PriceGapParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(PriceGapParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.ElderRayMAParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(ElderRayMAParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.FramaParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(FramaParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.HeikenAshiParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(HeikenAshiParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.KstOscillatorParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(KstOscillatorParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.LinearRegressionChannelsParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(LinearRegressionChannelsParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.MassIndexParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(MassIndexParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.MomentumPinballParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(MomentumPinballParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.MomentumSmaCrossoverParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(MomentumSmaCrossoverParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.PivotParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(PivotParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.RviParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(RviParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.KlingerVolumeParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(KlingerVolumeParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.VolatilityStopParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(VolatilityStopParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.TickVolumeAnalysisParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(TickVolumeAnalysisParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.CmoMfiParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(CmoMfiParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        "type.googleapis.com/strategies.RocMaCrossoverParameters" -> {
                            val builder = StringBuilder()
                            TextFormat.printer().print(
                                any.unpack(RocMaCrossoverParameters::class.java),
                                builder
                            )
                            builder.toString()
                        }
                        else -> {
                            logger.atWarning().log("Unknown parameter type: ${any.typeUrl}")
                            createErrorJson("unknown parameter type: ${any.typeUrl}")
                        }
                    }

                // Replace newlines and tabs with spaces for CSV compatibility
                textProtoString.replace("\n", " ").replace("\t", " ").trim()
            }
        } catch (e: Exception) {
            logger.atWarning().withCause(e).log("Error formatting parameters to textproto")
            createErrorJson("formatting error: ${e.message}")
        }

    private fun createFallbackJson(any: Any): String {
        val jsonObject = JsonObject()
        jsonObject.addProperty(
            "base64_data",
            java.util.Base64
                .getEncoder()
                .encodeToString(any.value.toByteArray()),
        )
        jsonObject.addProperty("type_url", any.typeUrl)
        return jsonObject.toString()
    }

    private fun createErrorJson(errorMessage: String): String {
        val jsonObject = JsonObject()
        jsonObject.addProperty("error", errorMessage)
        return jsonObject.toString()
    }

    private fun validateAndReturnJson(
        jsonString: String,
        typeUrl: String,
    ): String =
        try {
            // Parse the JSON to ensure it's valid
            JsonParser.parseString(jsonString)
            jsonString
        } catch (e: Exception) {
            logger.atWarning().withCause(e).log(
                "Generated JSON for $typeUrl is invalid: '$jsonString'",
            )
            createErrorJson("invalid json")
        }
}
