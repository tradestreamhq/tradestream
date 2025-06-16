package com.verlumen.tradestream.strategies

import com.google.protobuf.Any
import com.google.protobuf.InvalidProtocolBufferException
import com.verlumen.tradestream.strategies.adxstochastic.AdxStochasticParamConfig
import com.verlumen.tradestream.strategies.adxstochastic.AdxStochasticStrategyFactory
import com.verlumen.tradestream.strategies.emamacd.EmaMacdParamConfig
import com.verlumen.tradestream.strategies.emamacd.EmaMacdStrategyFactory
import com.verlumen.tradestream.strategies.movingaverages.doubleemacrossover.DoubleEmaCrossoverParamConfig
import com.verlumen.tradestream.strategies.movingaverages.doubleemacrossover.DoubleEmaCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.movingaverages.momentumsmarrossover.MomentumSmaCrossoverParamConfig
import com.verlumen.tradestream.strategies.movingaverages.momentumsmarrossover.MomentumSmaCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.movingaverages.smaemacrossover.SmaEmaCrossoverParamConfig
import com.verlumen.tradestream.strategies.movingaverages.smaemacrossover.SmaEmaCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.movingaverages.tripleemacrossover.TripleEmaCrossoverParamConfig
import com.verlumen.tradestream.strategies.movingaverages.tripleemacrossover.TripleEmaCrossoverStrategyFactory
import com.verlumen.tradestream.strategies.aroonmfi.AroonMfiParamConfig
import com.verlumen.tradestream.strategies.aroonmfi.AroonMfiStrategyFactory
import com.verlumen.tradestream.strategies.ichimokucloud.IchimokuCloudParamConfig
import com.verlumen.tradestream.strategies.ichimokucloud.IchimokuCloudStrategyFactory
import com.verlumen.tradestream.strategies.parabolicsar.ParabolicSarParamConfig
import com.verlumen.tradestream.strategies.parabolicsar.ParabolicSarStrategyFactory
import com.verlumen.tradestream.strategies.smarsi.SmaRsiParamConfig
import com.verlumen.tradestream.strategies.smarsi.SmaRsiStrategyFactory
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
        StrategyType.DOUBLE_EMA_CROSSOVER to
            StrategySpec(
                paramConfig = DoubleEmaCrossoverParamConfig(),
                strategyFactory = DoubleEmaCrossoverStrategyFactory(),
            ),
        StrategyType.MOMENTUM_SMA_CROSSOVER to
            StrategySpec(
                paramConfig = MomentumSmaCrossoverParamConfig(),
                strategyFactory = MomentumSmaCrossoverStrategyFactory(),
            ),
        StrategyType.SMA_EMA_CROSSOVER to
            StrategySpec(
                paramConfig = SmaEmaCrossoverParamConfig(),
                strategyFactory = SmaEmaCrossoverStrategyFactory(),
            ),
        StrategyType.TRIPLE_EMA_CROSSOVER to
            StrategySpec(
                paramConfig = TripleEmaCrossoverParamConfig(),
                strategyFactory = TripleEmaCrossoverStrategyFactory(),
            ),
        StrategyType.AROON_MFI to
            StrategySpec(
                paramConfig = AroonMfiParamConfig(),
                strategyFactory = AroonMfiStrategyFactory(),
            ),
        StrategyType.ICHIMOKU_CLOUD to
            StrategySpec(
                paramConfig = IchimokuCloudParamConfig(),
                strategyFactory = IchimokuCloudStrategyFactory(),
            ),
        StrategyType.PARABOLIC_SAR to
            StrategySpec(
                paramConfig = ParabolicSarParamConfig(),
                strategyFactory = ParabolicSarStrategyFactory(),
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
