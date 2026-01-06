package com.verlumen.tradestream.strategies

import com.verlumen.tradestream.strategies.adxdmi.AdxDmiParamConfig
import com.verlumen.tradestream.strategies.adxdmi.AdxDmiStrategyFactory
import com.verlumen.tradestream.strategies.adxstochastic.AdxStochasticParamConfig
import com.verlumen.tradestream.strategies.adxstochastic.AdxStochasticStrategyFactory
import com.verlumen.tradestream.strategies.aroonmfi.AroonMfiParamConfig
import com.verlumen.tradestream.strategies.aroonmfi.AroonMfiStrategyFactory
import com.verlumen.tradestream.strategies.atrcci.AtrCciParamConfig
import com.verlumen.tradestream.strategies.atrcci.AtrCciStrategyFactory
import com.verlumen.tradestream.strategies.atrtrailingstop.AtrTrailingStopParamConfig
import com.verlumen.tradestream.strategies.atrtrailingstop.AtrTrailingStopStrategyFactory
import com.verlumen.tradestream.strategies.awesomeoscillator.AwesomeOscillatorParamConfig
import com.verlumen.tradestream.strategies.awesomeoscillator.AwesomeOscillatorStrategyFactory
import com.verlumen.tradestream.strategies.bbandwr.BbandWRParamConfig
import com.verlumen.tradestream.strategies.bbandwr.BbandWRStrategyFactory
import com.verlumen.tradestream.strategies.chaikinoscillator.ChaikinOscillatorParamConfig
import com.verlumen.tradestream.strategies.chaikinoscillator.ChaikinOscillatorStrategyFactory
import com.verlumen.tradestream.strategies.cmfzeroline.CmfZeroLineParamConfig
import com.verlumen.tradestream.strategies.cmfzeroline.CmfZeroLineStrategyFactory
import com.verlumen.tradestream.strategies.cmomfi.CmoMfiParamConfig
import com.verlumen.tradestream.strategies.cmomfi.CmoMfiStrategyFactory
import com.verlumen.tradestream.strategies.dematemacrossover.DemaTemaCrossoverParamConfig
import com.verlumen.tradestream.strategies.dematemacrossover.DemaTemaCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.donchianbreakout.DonchianBreakoutParamConfig
import com.verlumen.tradestream.strategies.donchianbreakout.DonchianBreakoutStrategyFactory
import com.verlumen.tradestream.strategies.doubleemacrossover.DoubleEmaCrossoverParamConfig
import com.verlumen.tradestream.strategies.doubleemacrossover.DoubleEmaCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.doubletopbottom.DoubleTopBottomParamConfig
import com.verlumen.tradestream.strategies.doubletopbottom.DoubleTopBottomStrategyFactory
import com.verlumen.tradestream.strategies.dpocrossover.DpoCrossoverParamConfig
import com.verlumen.tradestream.strategies.dpocrossover.DpoCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.elderrayma.ElderRayMAParamConfig
import com.verlumen.tradestream.strategies.elderrayma.ElderRayMAStrategyFactory
import com.verlumen.tradestream.strategies.emamacd.EmaMacdParamConfig
import com.verlumen.tradestream.strategies.emamacd.EmaMacdStrategyFactory
import com.verlumen.tradestream.strategies.fibonacciretracements.FibonacciRetracementsParamConfig
import com.verlumen.tradestream.strategies.fibonacciretracements.FibonacciRetracementsStrategyFactory
import com.verlumen.tradestream.strategies.frama.FramaParamConfig
import com.verlumen.tradestream.strategies.frama.FramaStrategyFactory
import com.verlumen.tradestream.strategies.gannswing.GannSwingParamConfig
import com.verlumen.tradestream.strategies.gannswing.GannSwingStrategyFactory
import com.verlumen.tradestream.strategies.heikenashi.HeikenAshiParamConfig
import com.verlumen.tradestream.strategies.heikenashi.HeikenAshiStrategyFactory
import com.verlumen.tradestream.strategies.ichimokucloud.IchimokuCloudParamConfig
import com.verlumen.tradestream.strategies.ichimokucloud.IchimokuCloudStrategyFactory
import com.verlumen.tradestream.strategies.klingervolume.KlingerVolumeParamConfig
import com.verlumen.tradestream.strategies.klingervolume.KlingerVolumeStrategyFactory
import com.verlumen.tradestream.strategies.kstoscillator.KstOscillatorParamConfig
import com.verlumen.tradestream.strategies.kstoscillator.KstOscillatorStrategyFactory
import com.verlumen.tradestream.strategies.linearregressionchannels.LinearRegressionChannelsParamConfig
import com.verlumen.tradestream.strategies.linearregressionchannels.LinearRegressionChannelsStrategyFactory
import com.verlumen.tradestream.strategies.macdcrossover.MacdCrossoverParamConfig
import com.verlumen.tradestream.strategies.macdcrossover.MacdCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.massindex.MassIndexParamConfig
import com.verlumen.tradestream.strategies.massindex.MassIndexStrategyFactory
import com.verlumen.tradestream.strategies.momentumpinball.MomentumPinballParamConfig
import com.verlumen.tradestream.strategies.momentumpinball.MomentumPinballStrategyFactory
import com.verlumen.tradestream.strategies.momentumsmacrossover.MomentumSmaCrossoverParamConfig
import com.verlumen.tradestream.strategies.momentumsmacrossover.MomentumSmaCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.obvema.ObvEmaParamConfig
import com.verlumen.tradestream.strategies.obvema.ObvEmaStrategyFactory
import com.verlumen.tradestream.strategies.parabolicsarr.ParabolicSarParamConfig
import com.verlumen.tradestream.strategies.parabolicsarr.ParabolicSarStrategyFactory
import com.verlumen.tradestream.strategies.pivot.PivotParamConfig
import com.verlumen.tradestream.strategies.pivot.PivotStrategyFactory
import com.verlumen.tradestream.strategies.pricegap.PriceGapParamConfig
import com.verlumen.tradestream.strategies.pricegap.PriceGapStrategyFactory
import com.verlumen.tradestream.strategies.priceoscillatorsignal.PriceOscillatorSignalParamConfig
import com.verlumen.tradestream.strategies.priceoscillatorsignal.PriceOscillatorSignalStrategyFactory
import com.verlumen.tradestream.strategies.pvt.PvtParamConfig
import com.verlumen.tradestream.strategies.pvt.PvtStrategyFactory
import com.verlumen.tradestream.strategies.rainbowoscillator.RainbowOscillatorParamConfig
import com.verlumen.tradestream.strategies.rainbowoscillator.RainbowOscillatorStrategyFactory
import com.verlumen.tradestream.strategies.rangebars.RangeBarsParamConfig
import com.verlumen.tradestream.strategies.rangebars.RangeBarsStrategyFactory
import com.verlumen.tradestream.strategies.regressionchannel.RegressionChannelParamConfig
import com.verlumen.tradestream.strategies.regressionchannel.RegressionChannelStrategyFactory
import com.verlumen.tradestream.strategies.renkochart.RenkoChartParamConfig
import com.verlumen.tradestream.strategies.renkochart.RenkoChartStrategyFactory
import com.verlumen.tradestream.strategies.rocma.RocMaCrossoverParamConfig
import com.verlumen.tradestream.strategies.rocma.RocMaCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.rsiemacrossover.RsiEmaCrossoverParamConfig
import com.verlumen.tradestream.strategies.rsiemacrossover.RsiEmaCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.rvi.RviParamConfig
import com.verlumen.tradestream.strategies.rvi.RviStrategyFactory
import com.verlumen.tradestream.strategies.sarmfi.SarMfiParamConfig
import com.verlumen.tradestream.strategies.sarmfi.SarMfiStrategyFactory
import com.verlumen.tradestream.strategies.smaemacrossover.SmaEmaCrossoverParamConfig
import com.verlumen.tradestream.strategies.smaemacrossover.SmaEmaCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.smarsi.SmaRsiParamConfig
import com.verlumen.tradestream.strategies.smarsi.SmaRsiStrategyFactory
import com.verlumen.tradestream.strategies.stochasticema.StochasticEmaParamConfig
import com.verlumen.tradestream.strategies.stochasticema.StochasticEmaStrategyFactory
import com.verlumen.tradestream.strategies.stochasticsrsi.StochasticRsiParamConfig
import com.verlumen.tradestream.strategies.stochasticsrsi.StochasticRsiStrategyFactory
import com.verlumen.tradestream.strategies.tickvolumeanalysis.TickVolumeAnalysisParamConfig
import com.verlumen.tradestream.strategies.tickvolumeanalysis.TickVolumeAnalysisStrategyFactory
import com.verlumen.tradestream.strategies.tripleemacrossover.TripleEmaCrossoverParamConfig
import com.verlumen.tradestream.strategies.tripleemacrossover.TripleEmaCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.trixsignalline.TrixSignalLineParamConfig
import com.verlumen.tradestream.strategies.trixsignalline.TrixSignalLineStrategyFactory
import com.verlumen.tradestream.strategies.variableperiodema.VariablePeriodEmaParamConfig
import com.verlumen.tradestream.strategies.variableperiodema.VariablePeriodEmaStrategyFactory
import com.verlumen.tradestream.strategies.volatilitystop.VolatilityStopParamConfig
import com.verlumen.tradestream.strategies.volatilitystop.VolatilityStopStrategyFactory
import com.verlumen.tradestream.strategies.volumebreakout.VolumeBreakoutParamConfig
import com.verlumen.tradestream.strategies.volumebreakout.VolumeBreakoutStrategyFactory
import com.verlumen.tradestream.strategies.volumeprofile.VolumeProfileParamConfig
import com.verlumen.tradestream.strategies.volumeprofile.VolumeProfileStrategyFactory
import com.verlumen.tradestream.strategies.volumeprofiledeviations.VolumeProfileDeviationsParamConfig
import com.verlumen.tradestream.strategies.volumeprofiledeviations.VolumeProfileDeviationsStrategyFactory
import com.verlumen.tradestream.strategies.volumespreadanalysis.VolumeSpreadAnalysisParamConfig
import com.verlumen.tradestream.strategies.volumespreadanalysis.VolumeSpreadAnalysisStrategyFactory
import com.verlumen.tradestream.strategies.volumeweightedmacd.VolumeWeightedMacdParamConfig
import com.verlumen.tradestream.strategies.volumeweightedmacd.VolumeWeightedMacdStrategyFactory
import com.verlumen.tradestream.strategies.vpt.VptParamConfig
import com.verlumen.tradestream.strategies.vpt.VptStrategyFactory
import com.verlumen.tradestream.strategies.vwapcrossover.VwapCrossoverParamConfig
import com.verlumen.tradestream.strategies.vwapcrossover.VwapCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.vwapmeanreversion.VwapMeanReversionParamConfig
import com.verlumen.tradestream.strategies.vwapmeanreversion.VwapMeanReversionStrategyFactory

/**
 * The single source of truth for all implemented strategy specifications.
 * Uses string-based strategy names (e.g., "MACD_CROSSOVER") as keys.
 */
private val strategySpecMap: Map<String, StrategySpec> =
    mapOf(
        "ADX_STOCHASTIC" to
            StrategySpec(
                paramConfig = AdxStochasticParamConfig(),
                strategyFactory = AdxStochasticStrategyFactory(),
            ),
        "SMA_RSI" to
            StrategySpec(
                paramConfig = SmaRsiParamConfig(),
                strategyFactory = SmaRsiStrategyFactory(),
            ),
        "EMA_MACD" to
            StrategySpec(
                paramConfig = EmaMacdParamConfig(),
                strategyFactory = EmaMacdStrategyFactory(),
            ),
        "ATR_CCI" to
            StrategySpec(
                paramConfig = AtrCciParamConfig(),
                strategyFactory = AtrCciStrategyFactory(),
            ),
        "ATR_TRAILING_STOP" to
            StrategySpec(
                paramConfig = AtrTrailingStopParamConfig(),
                strategyFactory = AtrTrailingStopStrategyFactory(),
            ),
        "BBAND_W_R" to
            StrategySpec(
                paramConfig = BbandWRParamConfig(),
                strategyFactory = BbandWRStrategyFactory(),
            ),
        "CHAIKIN_OSCILLATOR" to
            StrategySpec(
                paramConfig = ChaikinOscillatorParamConfig(),
                strategyFactory = ChaikinOscillatorStrategyFactory(),
            ),
        "CMF_ZERO_LINE" to
            StrategySpec(
                paramConfig = CmfZeroLineParamConfig(),
                strategyFactory = CmfZeroLineStrategyFactory(),
            ),
        "CMO_MFI" to
            StrategySpec(
                paramConfig = CmoMfiParamConfig(),
                strategyFactory = CmoMfiStrategyFactory(),
            ),
        "DONCHIAN_BREAKOUT" to
            StrategySpec(
                paramConfig = DonchianBreakoutParamConfig(),
                strategyFactory = DonchianBreakoutStrategyFactory(),
            ),
        "DOUBLE_EMA_CROSSOVER" to
            StrategySpec(
                paramConfig = DoubleEmaCrossoverParamConfig(),
                strategyFactory = DoubleEmaCrossoverStrategyFactory(),
            ),
        "HEIKEN_ASHI" to
            StrategySpec(
                paramConfig = HeikenAshiParamConfig(),
                strategyFactory = HeikenAshiStrategyFactory(),
            ),
        "ICHIMOKU_CLOUD" to
            StrategySpec(
                paramConfig = IchimokuCloudParamConfig(),
                strategyFactory = IchimokuCloudStrategyFactory(),
            ),
        "MACD_CROSSOVER" to
            StrategySpec(
                paramConfig = MacdCrossoverParamConfig(),
                strategyFactory = MacdCrossoverStrategyFactory(),
            ),
        "MOMENTUM_PINBALL" to
            StrategySpec(
                paramConfig = MomentumPinballParamConfig(),
                strategyFactory = MomentumPinballStrategyFactory(),
            ),
        "MOMENTUM_SMA_CROSSOVER" to
            StrategySpec(
                paramConfig = MomentumSmaCrossoverParamConfig(),
                strategyFactory = MomentumSmaCrossoverStrategyFactory(),
            ),
        "PARABOLIC_SAR" to
            StrategySpec(
                paramConfig = ParabolicSarParamConfig(),
                strategyFactory = ParabolicSarStrategyFactory(),
            ),
        "RSI_EMA_CROSSOVER" to
            StrategySpec(
                paramConfig = RsiEmaCrossoverParamConfig(),
                strategyFactory = RsiEmaCrossoverStrategyFactory(),
            ),
        "RVI" to
            StrategySpec(
                paramConfig = RviParamConfig(),
                strategyFactory = RviStrategyFactory(),
            ),
        "SMA_EMA_CROSSOVER" to
            StrategySpec(
                paramConfig = SmaEmaCrossoverParamConfig(),
                strategyFactory = SmaEmaCrossoverStrategyFactory(),
            ),
        "STOCHASTIC_RSI" to
            StrategySpec(
                paramConfig = StochasticRsiParamConfig(),
                strategyFactory = StochasticRsiStrategyFactory(),
            ),
        "TICK_VOLUME_ANALYSIS" to
            StrategySpec(
                paramConfig = TickVolumeAnalysisParamConfig(),
                strategyFactory = TickVolumeAnalysisStrategyFactory(),
            ),
        "TRIPLE_EMA_CROSSOVER" to
            StrategySpec(
                paramConfig = TripleEmaCrossoverParamConfig(),
                strategyFactory = TripleEmaCrossoverStrategyFactory(),
            ),
        "VOLATILITY_STOP" to
            StrategySpec(
                paramConfig = VolatilityStopParamConfig(),
                strategyFactory = VolatilityStopStrategyFactory(),
            ),
        "VOLUME_WEIGHTED_MACD" to
            StrategySpec(
                paramConfig = VolumeWeightedMacdParamConfig(),
                strategyFactory = VolumeWeightedMacdStrategyFactory(),
            ),
        "VWAP_CROSSOVER" to
            StrategySpec(
                paramConfig = VwapCrossoverParamConfig(),
                strategyFactory = VwapCrossoverStrategyFactory(),
            ),
        "KST_OSCILLATOR" to
            StrategySpec(
                paramConfig = KstOscillatorParamConfig(),
                strategyFactory = KstOscillatorStrategyFactory(),
            ),
        "MASS_INDEX" to
            StrategySpec(
                paramConfig = MassIndexParamConfig(),
                strategyFactory = MassIndexStrategyFactory(),
            ),
        "ADX_DMI" to
            StrategySpec(
                paramConfig = AdxDmiParamConfig(),
                strategyFactory = AdxDmiStrategyFactory(),
            ),
        "LINEAR_REGRESSION_CHANNELS" to
            StrategySpec(
                paramConfig = LinearRegressionChannelsParamConfig(),
                strategyFactory = LinearRegressionChannelsStrategyFactory(),
            ),
        "VWAP_MEAN_REVERSION" to
            StrategySpec(
                paramConfig = VwapMeanReversionParamConfig(),
                strategyFactory = VwapMeanReversionStrategyFactory(),
            ),
        "STOCHASTIC_EMA" to
            StrategySpec(
                paramConfig = StochasticEmaParamConfig(),
                strategyFactory = StochasticEmaStrategyFactory(),
            ),
        "OBV_EMA" to
            StrategySpec(
                paramConfig = ObvEmaParamConfig(),
                strategyFactory = ObvEmaStrategyFactory(),
            ),
        "KLINGER_VOLUME" to
            StrategySpec(
                paramConfig = KlingerVolumeParamConfig(),
                strategyFactory = KlingerVolumeStrategyFactory(),
            ),
        "VOLUME_BREAKOUT" to
            StrategySpec(
                paramConfig = VolumeBreakoutParamConfig(),
                strategyFactory = VolumeBreakoutStrategyFactory(),
            ),
        "PVT" to
            StrategySpec(
                paramConfig = PvtParamConfig(),
                strategyFactory = PvtStrategyFactory(),
            ),
        "VPT" to
            StrategySpec(
                paramConfig = VptParamConfig(),
                strategyFactory = VptStrategyFactory(),
            ),
        "VOLUME_SPREAD_ANALYSIS" to
            StrategySpec(
                paramConfig = VolumeSpreadAnalysisParamConfig(),
                strategyFactory = VolumeSpreadAnalysisStrategyFactory(),
            ),
        "TRIX_SIGNAL_LINE" to
            StrategySpec(
                paramConfig = TrixSignalLineParamConfig(),
                strategyFactory = TrixSignalLineStrategyFactory(),
            ),
        "AROON_MFI" to
            StrategySpec(
                paramConfig = AroonMfiParamConfig(),
                strategyFactory = AroonMfiStrategyFactory(),
            ),
        "AWESOME_OSCILLATOR" to
            StrategySpec(
                paramConfig = AwesomeOscillatorParamConfig(),
                strategyFactory = AwesomeOscillatorStrategyFactory(),
            ),
        "DEMA_TEMA_CROSSOVER" to
            StrategySpec(
                paramConfig = DemaTemaCrossoverParamConfig(),
                strategyFactory = DemaTemaCrossoverStrategyFactory(),
            ),
        "ELDER_RAY_MA" to
            StrategySpec(
                paramConfig = ElderRayMAParamConfig(),
                strategyFactory = ElderRayMAStrategyFactory(),
            ),
        "FRAMA" to
            StrategySpec(
                paramConfig = FramaParamConfig(),
                strategyFactory = FramaStrategyFactory(),
            ),
        "RAINBOW_OSCILLATOR" to
            StrategySpec(
                paramConfig = RainbowOscillatorParamConfig(),
                strategyFactory = RainbowOscillatorStrategyFactory(),
            ),
        "PRICE_OSCILLATOR_SIGNAL" to
            StrategySpec(
                paramConfig = PriceOscillatorSignalParamConfig(),
                strategyFactory = PriceOscillatorSignalStrategyFactory(),
            ),
        "ROC_MA_CROSSOVER" to
            StrategySpec(
                paramConfig = RocMaCrossoverParamConfig(),
                strategyFactory = RocMaCrossoverStrategyFactory(),
            ),
        "REGRESSION_CHANNEL" to
            StrategySpec(
                paramConfig = RegressionChannelParamConfig(),
                strategyFactory = RegressionChannelStrategyFactory(),
            ),
        "PIVOT" to
            StrategySpec(
                paramConfig = PivotParamConfig(),
                strategyFactory = PivotStrategyFactory(),
            ),
        "DOUBLE_TOP_BOTTOM" to
            StrategySpec(
                paramConfig = DoubleTopBottomParamConfig(),
                strategyFactory = DoubleTopBottomStrategyFactory(),
            ),
        "FIBONACCI_RETRACEMENTS" to
            StrategySpec(
                paramConfig = FibonacciRetracementsParamConfig(),
                strategyFactory = FibonacciRetracementsStrategyFactory(),
            ),
        "PRICE_GAP" to
            StrategySpec(
                paramConfig = PriceGapParamConfig(),
                strategyFactory = PriceGapStrategyFactory(),
            ),
        "RENKO_CHART" to
            StrategySpec(
                RenkoChartParamConfig(),
                RenkoChartStrategyFactory(),
            ),
        "RANGE_BARS" to
            StrategySpec(
                paramConfig = RangeBarsParamConfig(),
                strategyFactory = RangeBarsStrategyFactory(),
            ),
        "GANN_SWING" to
            StrategySpec(
                paramConfig = GannSwingParamConfig(),
                strategyFactory = GannSwingStrategyFactory(),
            ),
        "SAR_MFI" to
            StrategySpec(
                paramConfig = SarMfiParamConfig(),
                strategyFactory = SarMfiStrategyFactory(),
            ),
        "DPO_CROSSOVER" to
            StrategySpec(
                paramConfig = DpoCrossoverParamConfig(),
                strategyFactory = DpoCrossoverStrategyFactory(),
            ),
        "VARIABLE_PERIOD_EMA" to
            StrategySpec(
                paramConfig = VariablePeriodEmaParamConfig(),
                strategyFactory = VariablePeriodEmaStrategyFactory(),
            ),
        "VOLUME_PROFILE" to
            StrategySpec(
                paramConfig = VolumeProfileParamConfig(),
                strategyFactory = VolumeProfileStrategyFactory(),
            ),
        "VOLUME_PROFILE_DEVIATIONS" to
            StrategySpec(
                paramConfig = VolumeProfileDeviationsParamConfig(),
                strategyFactory = VolumeProfileDeviationsStrategyFactory(),
            ),
        // To add a new strategy, just add a new entry here.
    )

/**
 * Central registry for strategy specifications.
 *
 * Provides string-based lookup using the strategySpecMap.
 * All code should use [StrategySpecs.getSpec] with string strategy names.
 */
object StrategySpecs {
    /**
     * Gets the StrategySpec for the given strategy name.
     *
     * @param strategyName The name of the strategy (e.g., "MACD_CROSSOVER")
     * @return The StrategySpec for the strategy
     * @throws NoSuchElementException if the strategy is not found
     */
    @JvmStatic
    fun getSpec(strategyName: String): StrategySpec =
        strategySpecMap[strategyName]
            ?: throw NoSuchElementException("Strategy not found: $strategyName")

    /**
     * Gets the StrategySpec for the given strategy name, or null if not found.
     *
     * @param strategyName The name of the strategy
     * @return The StrategySpec, or null if not found
     */
    @JvmStatic
    fun getSpecOrNull(strategyName: String): StrategySpec? = strategySpecMap[strategyName]

    /**
     * Checks if a strategy with the given name is supported.
     *
     * @param strategyName The name of the strategy
     * @return true if the strategy is available
     */
    @JvmStatic
    fun isSupported(strategyName: String): Boolean = strategySpecMap.containsKey(strategyName)

    /**
     * Returns a list of all supported strategy names.
     *
     * @return List of strategy names, sorted alphabetically
     */
    @JvmStatic
    fun getSupportedStrategyNames(): List<String> = strategySpecMap.keys.sorted()

    /**
     * Returns the number of supported strategies.
     *
     * @return The count of all available strategies
     */
    @JvmStatic
    fun size(): Int = strategySpecMap.size
}
