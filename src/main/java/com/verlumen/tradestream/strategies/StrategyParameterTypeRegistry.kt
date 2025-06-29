package com.verlumen.tradestream.strategies

import com.google.common.flogger.FluentLogger
import com.google.gson.JsonParser
import com.google.protobuf.Any
import com.google.protobuf.util.JsonFormat
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

    fun formatParametersToJson(any: Any): String =
        try {
            if (any.typeUrl.isNullOrBlank() || any.value == com.google.protobuf.ByteString.EMPTY) {
                "error: \"empty parameters\""
            } else {
                val jsonString =
                    when (any.typeUrl) {
                        "type.googleapis.com/strategies.SmaRsiParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(SmaRsiParameters::class.java),
                            )
                        "type.googleapis.com/strategies.EmaMacdParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(EmaMacdParameters::class.java),
                            )
                        "type.googleapis.com/strategies.AdxStochasticParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(AdxStochasticParameters::class.java),
                            )
                        "type.googleapis.com/strategies.AroonMfiParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(AroonMfiParameters::class.java),
                            )
                        "type.googleapis.com/strategies.IchimokuCloudParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(IchimokuCloudParameters::class.java),
                            )
                        "type.googleapis.com/strategies.ParabolicSarParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(ParabolicSarParameters::class.java),
                            )
                        "type.googleapis.com/strategies.SmaEmaCrossoverParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(SmaEmaCrossoverParameters::class.java),
                            )
                        "type.googleapis.com/strategies.DoubleEmaCrossoverParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(DoubleEmaCrossoverParameters::class.java),
                            )
                        "type.googleapis.com/strategies.TripleEmaCrossoverParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(TripleEmaCrossoverParameters::class.java),
                            )
                        "type.googleapis.com/strategies.MacdCrossoverParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(MacdCrossoverParameters::class.java),
                            )
                        "type.googleapis.com/strategies.RsiEmaCrossoverParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(RsiEmaCrossoverParameters::class.java),
                            )
                        "type.googleapis.com/strategies.StochasticEmaParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(StochasticEmaParameters::class.java),
                            )
                        "type.googleapis.com/strategies.StochasticRsiParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(StochasticRsiParameters::class.java),
                            )
                        "type.googleapis.com/strategies.VwapCrossoverParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(VwapCrossoverParameters::class.java),
                            )
                        "type.googleapis.com/strategies.VwapMeanReversionParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(VwapMeanReversionParameters::class.java),
                            )
                        "type.googleapis.com/strategies.VolumeWeightedMacdParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(VolumeWeightedMacdParameters::class.java),
                            )
                        "type.googleapis.com/strategies.ObvEmaParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(ObvEmaParameters::class.java),
                            )
                        "type.googleapis.com/strategies.PvtParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(PvtParameters::class.java),
                            )
                        "type.googleapis.com/strategies.VptParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(VptParameters::class.java),
                            )
                        "type.googleapis.com/strategies.VolumeBreakoutParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(VolumeBreakoutParameters::class.java),
                            )
                        "type.googleapis.com/strategies.VolumeSpreadAnalysisParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(VolumeSpreadAnalysisParameters::class.java),
                            )
                        "type.googleapis.com/strategies.TrixSignalLineParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(TrixSignalLineParameters::class.java),
                            )
                        "type.googleapis.com/strategies.DemaTemaCrossoverParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(DemaTemaCrossoverParameters::class.java),
                            )
                        "type.googleapis.com/strategies.AwesomeOscillatorParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(AwesomeOscillatorParameters::class.java),
                            )
                        "type.googleapis.com/strategies.RainbowOscillatorParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(RainbowOscillatorParameters::class.java),
                            )
                        "type.googleapis.com/strategies.RegressionChannelParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(RegressionChannelParameters::class.java),
                            )
                        "type.googleapis.com/strategies.PriceOscillatorSignalParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(PriceOscillatorSignalParameters::class.java),
                            )
                        "type.googleapis.com/strategies.RenkoChartParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(RenkoChartParameters::class.java),
                            )
                        "type.googleapis.com/strategies.RangeBarsParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(RangeBarsParameters::class.java),
                            )
                        "type.googleapis.com/strategies.GannSwingParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(GannSwingParameters::class.java),
                            )
                        "type.googleapis.com/strategies.SarMfiParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(SarMfiParameters::class.java),
                            )
                        "type.googleapis.com/strategies.DpoCrossoverParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(DpoCrossoverParameters::class.java),
                            )
                        "type.googleapis.com/strategies.VariablePeriodEmaParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(VariablePeriodEmaParameters::class.java),
                            )
                        "type.googleapis.com/strategies.VolumeProfileParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(VolumeProfileParameters::class.java),
                            )
                        "type.googleapis.com/strategies.VolumeProfileDeviationsParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(VolumeProfileDeviationsParameters::class.java),
                            )
                        "type.googleapis.com/strategies.AdxDmiParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(AdxDmiParameters::class.java),
                            )
                        "type.googleapis.com/strategies.AtrCciParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(AtrCciParameters::class.java),
                            )
                        "type.googleapis.com/strategies.AtrTrailingStopParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(AtrTrailingStopParameters::class.java),
                            )
                        "type.googleapis.com/strategies.BbandWRParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(BbandWRParameters::class.java),
                            )
                        "type.googleapis.com/strategies.ChaikinOscillatorParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(ChaikinOscillatorParameters::class.java),
                            )
                        "type.googleapis.com/strategies.CmfZeroLineParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(CmfZeroLineParameters::class.java),
                            )
                        "type.googleapis.com/strategies.CmoMfiParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(CmoMfiParameters::class.java),
                            )
                        "type.googleapis.com/strategies.DonchianBreakoutParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(DonchianBreakoutParameters::class.java),
                            )
                        "type.googleapis.com/strategies.DoubleTopBottomParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(DoubleTopBottomParameters::class.java),
                            )
                        "type.googleapis.com/strategies.ElderRayMAParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(ElderRayMAParameters::class.java),
                            )
                        "type.googleapis.com/strategies.FibonacciRetracementsParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(FibonacciRetracementsParameters::class.java),
                            )
                        "type.googleapis.com/strategies.FramaParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(FramaParameters::class.java),
                            )
                        "type.googleapis.com/strategies.HeikenAshiParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(HeikenAshiParameters::class.java),
                            )
                        "type.googleapis.com/strategies.KlingerVolumeParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(KlingerVolumeParameters::class.java),
                            )
                        "type.googleapis.com/strategies.KstOscillatorParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(KstOscillatorParameters::class.java),
                            )
                        "type.googleapis.com/strategies.LinearRegressionChannelsParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(LinearRegressionChannelsParameters::class.java),
                            )
                        "type.googleapis.com/strategies.MassIndexParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(MassIndexParameters::class.java),
                            )
                        "type.googleapis.com/strategies.MomentumPinballParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(MomentumPinballParameters::class.java),
                            )
                        "type.googleapis.com/strategies.MomentumSmaCrossoverParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(MomentumSmaCrossoverParameters::class.java),
                            )
                        "type.googleapis.com/strategies.PivotParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(PivotParameters::class.java),
                            )
                        "type.googleapis.com/strategies.PriceGapParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(PriceGapParameters::class.java),
                            )
                        "type.googleapis.com/strategies.RocMaCrossoverParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(RocMaCrossoverParameters::class.java),
                            )
                        "type.googleapis.com/strategies.RviParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(RviParameters::class.java),
                            )
                        "type.googleapis.com/strategies.TickVolumeAnalysisParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(TickVolumeAnalysisParameters::class.java),
                            )
                        "type.googleapis.com/strategies.VolatilityStopParameters" ->
                            JsonFormat.printer().omittingInsignificantWhitespace().print(
                                any.unpack(VolatilityStopParameters::class.java),
                            )
                        else -> {
                            logger.atWarning().log("Unknown parameter type: ${any.typeUrl}")
                            "error: \"unknown parameter type: ${any.typeUrl}\""
                        }
                    }
                jsonString
            }
        } catch (e: Exception) {
            logger.atSevere().withCause(e).log("Failed to format parameters to JSON")
            "error: \"${e.message}\""
        }

    fun validateJsonParameter(jsonString: String): Boolean =
        try {
            val jsonElement = JsonParser.parseString(jsonString)
            jsonElement.isJsonObject
        } catch (e: Exception) {
            logger.atWarning().withCause(e).log("Invalid JSON parameter: $jsonString")
            false
        }
}
