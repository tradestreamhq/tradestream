package com.verlumen.tradestream.strategies

import com.google.protobuf.Any
import com.google.protobuf.InvalidProtocolBufferException
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
import org.ta4j.core.BarSeries
import org.ta4j.core.Strategy

/**
 * The single source of truth for all implemented strategy specifications.
 * The map's keys define which strategies are considered "supported".
 */
private val strategySpecMap: Map<StrategyType, StrategySpec> =
    mapOf(
        StrategyType.ADX_STOCHASTIC to
            StrategySpec(
                paramConfig = AdxStochasticParamConfig(),
                strategyFactory = AdxStochasticStrategyFactory(),
            ),
        StrategyType.SMA_RSI to
            StrategySpec(
                paramConfig = SmaRsiParamConfig(),
                strategyFactory = SmaRsiStrategyFactory(),
            ),
        StrategyType.EMA_MACD to
            StrategySpec(
                paramConfig = EmaMacdParamConfig(),
                strategyFactory = EmaMacdStrategyFactory(),
            ),
        StrategyType.ATR_CCI to
            StrategySpec(
                paramConfig = AtrCciParamConfig(),
                strategyFactory = AtrCciStrategyFactory(),
            ),
        StrategyType.ATR_TRAILING_STOP to
            StrategySpec(
                paramConfig = AtrTrailingStopParamConfig(),
                strategyFactory = AtrTrailingStopStrategyFactory(),
            ),
        StrategyType.BBAND_W_R to
            StrategySpec(
                paramConfig = BbandWRParamConfig(),
                strategyFactory = BbandWRStrategyFactory(),
            ),
        StrategyType.CHAIKIN_OSCILLATOR to
            StrategySpec(
                paramConfig = ChaikinOscillatorParamConfig(),
                strategyFactory = ChaikinOscillatorStrategyFactory(),
            ),
        StrategyType.CMF_ZERO_LINE to
            StrategySpec(
                paramConfig = CmfZeroLineParamConfig(),
                strategyFactory = CmfZeroLineStrategyFactory(),
            ),
        StrategyType.CMO_MFI to
            StrategySpec(
                paramConfig = CmoMfiParamConfig(),
                strategyFactory = CmoMfiStrategyFactory(),
            ),
        StrategyType.DONCHIAN_BREAKOUT to
            StrategySpec(
                paramConfig = DonchianBreakoutParamConfig(),
                strategyFactory = DonchianBreakoutStrategyFactory(),
            ),
        StrategyType.DOUBLE_EMA_CROSSOVER to
            StrategySpec(
                paramConfig = DoubleEmaCrossoverParamConfig(),
                strategyFactory = DoubleEmaCrossoverStrategyFactory(),
            ),
        StrategyType.HEIKEN_ASHI to
            StrategySpec(
                paramConfig = HeikenAshiParamConfig(),
                strategyFactory = HeikenAshiStrategyFactory(),
            ),
        StrategyType.ICHIMOKU_CLOUD to
            StrategySpec(
                paramConfig = IchimokuCloudParamConfig(),
                strategyFactory = IchimokuCloudStrategyFactory(),
            ),
        StrategyType.MACD_CROSSOVER to
            StrategySpec(
                paramConfig = MacdCrossoverParamConfig(),
                strategyFactory = MacdCrossoverStrategyFactory(),
            ),
        StrategyType.MOMENTUM_PINBALL to
            StrategySpec(
                paramConfig = MomentumPinballParamConfig(),
                strategyFactory = MomentumPinballStrategyFactory(),
            ),
        StrategyType.MOMENTUM_SMA_CROSSOVER to
            StrategySpec(
                paramConfig = MomentumSmaCrossoverParamConfig(),
                strategyFactory = MomentumSmaCrossoverStrategyFactory(),
            ),
        StrategyType.PARABOLIC_SAR to
            StrategySpec(
                paramConfig = ParabolicSarParamConfig(),
                strategyFactory = ParabolicSarStrategyFactory(),
            ),
        StrategyType.RSI_EMA_CROSSOVER to
            StrategySpec(
                paramConfig = RsiEmaCrossoverParamConfig(),
                strategyFactory = RsiEmaCrossoverStrategyFactory(),
            ),
        StrategyType.RVI to
            StrategySpec(
                paramConfig = RviParamConfig(),
                strategyFactory = RviStrategyFactory(),
            ),
        StrategyType.SMA_EMA_CROSSOVER to
            StrategySpec(
                paramConfig = SmaEmaCrossoverParamConfig(),
                strategyFactory = SmaEmaCrossoverStrategyFactory(),
            ),
        StrategyType.STOCHASTIC_RSI to
            StrategySpec(
                paramConfig = StochasticRsiParamConfig(),
                strategyFactory = StochasticRsiStrategyFactory(),
            ),
        StrategyType.TICK_VOLUME_ANALYSIS to
            StrategySpec(
                paramConfig = TickVolumeAnalysisParamConfig(),
                strategyFactory = TickVolumeAnalysisStrategyFactory(),
            ),
        StrategyType.TRIPLE_EMA_CROSSOVER to
            StrategySpec(
                paramConfig = TripleEmaCrossoverParamConfig(),
                strategyFactory = TripleEmaCrossoverStrategyFactory(),
            ),
        StrategyType.VOLATILITY_STOP to
            StrategySpec(
                paramConfig = VolatilityStopParamConfig(),
                strategyFactory = VolatilityStopStrategyFactory(),
            ),
        StrategyType.VOLUME_WEIGHTED_MACD to
            StrategySpec(
                paramConfig = VolumeWeightedMacdParamConfig(),
                strategyFactory = VolumeWeightedMacdStrategyFactory(),
            ),
        StrategyType.VWAP_CROSSOVER to
            StrategySpec(
                paramConfig = VwapCrossoverParamConfig(),
                strategyFactory = VwapCrossoverStrategyFactory(),
            ),
        StrategyType.KST_OSCILLATOR to
            StrategySpec(
                paramConfig = KstOscillatorParamConfig(),
                strategyFactory = KstOscillatorStrategyFactory(),
            ),
        StrategyType.MASS_INDEX to
            StrategySpec(
                paramConfig = MassIndexParamConfig(),
                strategyFactory = MassIndexStrategyFactory(),
            ),
        StrategyType.ADX_DMI to
            StrategySpec(
                paramConfig = AdxDmiParamConfig(),
                strategyFactory = AdxDmiStrategyFactory(),
            ),
        StrategyType.LINEAR_REGRESSION_CHANNELS to
            StrategySpec(
                paramConfig = LinearRegressionChannelsParamConfig(),
                strategyFactory = LinearRegressionChannelsStrategyFactory(),
            ),
        StrategyType.VWAP_MEAN_REVERSION to
            StrategySpec(
                paramConfig = VwapMeanReversionParamConfig(),
                strategyFactory = VwapMeanReversionStrategyFactory(),
            ),
        StrategyType.STOCHASTIC_EMA to
            StrategySpec(
                paramConfig = StochasticEmaParamConfig(),
                strategyFactory = StochasticEmaStrategyFactory(),
            ),
        StrategyType.OBV_EMA to
            StrategySpec(
                paramConfig = ObvEmaParamConfig(),
                strategyFactory = ObvEmaStrategyFactory(),
            ),
        StrategyType.KLINGER_VOLUME to
            StrategySpec(
                paramConfig = KlingerVolumeParamConfig(),
                strategyFactory = KlingerVolumeStrategyFactory(),
            ),
        StrategyType.VOLUME_BREAKOUT to
            StrategySpec(
                paramConfig = VolumeBreakoutParamConfig(),
                strategyFactory = VolumeBreakoutStrategyFactory(),
            ),
        StrategyType.PVT to
            StrategySpec(
                paramConfig = PvtParamConfig(),
                strategyFactory = PvtStrategyFactory(),
            ),
        StrategyType.VPT to
            StrategySpec(
                paramConfig = VptParamConfig(),
                strategyFactory = VptStrategyFactory(),
            ),
        StrategyType.VOLUME_SPREAD_ANALYSIS to
            StrategySpec(
                paramConfig = VolumeSpreadAnalysisParamConfig(),
                strategyFactory = VolumeSpreadAnalysisStrategyFactory(),
            ),
        StrategyType.TRIX_SIGNAL_LINE to
            StrategySpec(
                paramConfig = TrixSignalLineParamConfig(),
                strategyFactory = TrixSignalLineStrategyFactory(),
            ),
        StrategyType.AROON_MFI to
            StrategySpec(
                paramConfig = AroonMfiParamConfig(),
                strategyFactory = AroonMfiStrategyFactory(),
            ),
        StrategyType.AWESOME_OSCILLATOR to
            StrategySpec(
                paramConfig = AwesomeOscillatorParamConfig(),
                strategyFactory = AwesomeOscillatorStrategyFactory(),
            ),
        StrategyType.DEMA_TEMA_CROSSOVER to
            StrategySpec(
                paramConfig = DemaTemaCrossoverParamConfig(),
                strategyFactory = DemaTemaCrossoverStrategyFactory(),
            ),
        StrategyType.ELDER_RAY_MA to
            StrategySpec(
                paramConfig = ElderRayMAParamConfig(),
                strategyFactory = ElderRayMAStrategyFactory(),
            ),
        StrategyType.FRAMA to
            StrategySpec(
                paramConfig = FramaParamConfig(),
                strategyFactory = FramaStrategyFactory(),
            ),
        StrategyType.RAINBOW_OSCILLATOR to
            StrategySpec(
                paramConfig = RainbowOscillatorParamConfig(),
                strategyFactory = RainbowOscillatorStrategyFactory(),
            ),
        StrategyType.PRICE_OSCILLATOR_SIGNAL to
            StrategySpec(
                paramConfig = PriceOscillatorSignalParamConfig(),
                strategyFactory = PriceOscillatorSignalStrategyFactory(),
            ),
        StrategyType.ROC_MA_CROSSOVER to
            StrategySpec(
                paramConfig = RocMaCrossoverParamConfig(),
                strategyFactory = RocMaCrossoverStrategyFactory(),
            ),
        StrategyType.REGRESSION_CHANNEL to
            StrategySpec(
                paramConfig = RegressionChannelParamConfig(),
                strategyFactory = RegressionChannelStrategyFactory(),
            ),
        StrategyType.PIVOT to
            StrategySpec(
                paramConfig = PivotParamConfig(),
                strategyFactory = PivotStrategyFactory(),
            ),
        StrategyType.DOUBLE_TOP_BOTTOM to
            StrategySpec(
                paramConfig = DoubleTopBottomParamConfig(),
                strategyFactory = DoubleTopBottomStrategyFactory(),
            ),
        StrategyType.FIBONACCI_RETRACEMENTS to
            StrategySpec(
                paramConfig = FibonacciRetracementsParamConfig(),
                strategyFactory = FibonacciRetracementsStrategyFactory(),
            ),
        StrategyType.PRICE_GAP to
            StrategySpec(
                paramConfig = PriceGapParamConfig(),
                strategyFactory = PriceGapStrategyFactory(),
            ),
        StrategyType.RENKO_CHART to
            StrategySpec(
                RenkoChartParamConfig(),
                RenkoChartStrategyFactory(),
            ),
        StrategyType.RANGE_BARS to
            StrategySpec(
                paramConfig = RangeBarsParamConfig(),
                strategyFactory = RangeBarsStrategyFactory(),
            ),
        StrategyType.GANN_SWING to
            StrategySpec(
                paramConfig = GannSwingParamConfig(),
                strategyFactory = GannSwingStrategyFactory(),
            ),
        StrategyType.SAR_MFI to
            StrategySpec(
                paramConfig = SarMfiParamConfig(),
                strategyFactory = SarMfiStrategyFactory(),
            ),
        StrategyType.DPO_CROSSOVER to
            StrategySpec(
                paramConfig = DpoCrossoverParamConfig(),
                strategyFactory = DpoCrossoverStrategyFactory(),
            ),
        StrategyType.VARIABLE_PERIOD_EMA to
            StrategySpec(
                paramConfig = VariablePeriodEmaParamConfig(),
                strategyFactory = VariablePeriodEmaStrategyFactory(),
            ),
        // To add a new strategy, just add a new entry here.
    )

/**
 * An extension property that retrieves the corresponding [StrategySpec] from the central map.
 *
 * @throws NotImplementedError if no spec is defined for the given strategy type.
 */
val StrategyType.spec: StrategySpec
    get() =
        strategySpecMap[this]
            ?: throw NotImplementedError("No StrategySpec defined for strategy type: $this")

/**
 * An extension function that returns `true` if a [StrategySpec] has been
 * implemented for this [StrategyType] by checking for its key in the central map.
 */
fun StrategyType.isSupported(): Boolean = strategySpecMap.containsKey(this)

/**
 * Extension function to create a new Ta4j Strategy instance using default parameters.
 *
 * @param barSeries the bar series to associate with the strategy
 * @return a new instance of a Ta4j Strategy configured with the default parameters
 * @throws InvalidProtocolBufferException if there is an error unpacking the default parameters
 */
@Throws(InvalidProtocolBufferException::class)
fun StrategyType.createStrategy(barSeries: BarSeries): Strategy = createStrategy(barSeries, getDefaultParameters())

/**
 * Extension function to create a new Ta4j Strategy instance using provided parameters.
 *
 * @param barSeries the bar series to associate with the strategy
 * @param parameters the configuration parameters for the strategy, wrapped in an Any message
 * @return a new instance of a Ta4j Strategy configured with the provided parameters
 * @throws InvalidProtocolBufferException if there is an error unpacking the parameters
 */
@Throws(InvalidProtocolBufferException::class)
fun StrategyType.createStrategy(
    barSeries: BarSeries,
    parameters: Any,
): Strategy = getStrategyFactory().createStrategy(barSeries, parameters)

/**
 * Extension function to retrieve the default configuration parameters for this strategy type.
 *
 * This method obtains the default parameters from the associated StrategyFactory and
 * packs them into a protocol buffers Any message.
 *
 * @return an Any message containing the default parameters for this strategy type
 */
fun StrategyType.getDefaultParameters(): Any = Any.pack(getStrategyFactory().getDefaultParameters())

/**
 * Extension function to retrieve the StrategyFactory corresponding to this strategy type.
 *
 * The returned factory is responsible for creating instances of the strategy as well as
 * providing its default configuration parameters.
 *
 * @return the StrategyFactory associated with this strategy type
 */
fun StrategyType.getStrategyFactory(): StrategyFactory<*> = this.spec.strategyFactory

/**
 * Returns a list of all supported strategy types.
 *
 * This list includes every available StrategyType that can be used to create and
 * configure trading strategies.
 *
 * @return a list of supported StrategyType instances
 */
fun getSupportedStrategyTypes(): List<StrategyType> = strategySpecMap.keys.toList()
