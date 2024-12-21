package com.verlumen.tradestream.strategies;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.Message;
import com.verlumen.tradestream.strategies.StrategyType;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;

/**
 * A factory interface for creating {@link Strategy} instances from provided parameters.
 * Implementations of this interface are responsible for instantiating a specific type of
 * trading strategy based on configuration data, often represented as a Protocol Buffer message.
 *
 * @param <T> The specific type of {@link Message} that holds the parameters for the strategy.
 */
public interface StrategyFactory<T extends Message> {
  /**
   * Creates a Ta4j Strategy object from the provided {@link BarSeries} and parameters.
   *
   * @param series     The {@link BarSeries} to associate with the created strategy.
   * @param parameters The parameters for configuring the strategy.
   * @return The created {@link Strategy} object.
   * @throws InvalidProtocolBufferException If there is an error when unpacking the parameters.
   */
  Strategy createStrategy(BarSeries series, T parameters) throws InvalidProtocolBufferException;

  /**
   * Creates a Ta4j Strategy object from the provided {@link BarSeries} and parameters.
   * This is a convenience method that unpacks the parameters from an {@link Any} message
   * before invoking {@link #createStrategy(BarSeries, Message)}.
   *
   * @param series     The {@link BarSeries} to associate with the created strategy.
   * @param parameters The parameters for the strategy wrapped in an {@link Any} message.
   * @return The created {@link Strategy} object.
   * @throws InvalidProtocolBufferException If there is an error when unpacking the {@link Any} message.
   */
  default Strategy createStrategy(BarSeries series, Any parameters) throws InvalidProtocolBufferException {
    return createStrategy(series, parameters.unpack(getParameterClass()));
  }

  default Strategy createStrategy(Rule entryRule, Rule exitRule) {
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator shortEma = new EMAIndicator(closePrice, params.getShortEmaPeriod());
    EMAIndicator longEma = new EMAIndicator(closePrice, params.getLongEmaPeriod());

    return new BaseStrategy(getStrategyType().name(), entryRule, exitRule);
  }
  
  /**
   * Creates a Ta4j Strategy object from the provided {@link Rule} and {@link Rule}.
   *
   * @param entryRule     The {@link Rule} that signals an entry into a position.
   * @param exitRule The {@link Rule} that signals an exit from a position.
   * @return The created {@link Strategy} object.
   */
  default Strategy createStrategy(BarSeries series, Rule entryRule, Rule exitRule) {
    return new BaseStrategy(getStrategyType().name(), entryRule, exitRule);
  }
  
  /**
   * Gets the {@link StrategyType} that this factory handles.
   *
   * @return The {@link StrategyType} this factory is responsible for creating.
   */
  StrategyType getStrategyType();

  /**
   * Returns the {@link Class} of the parameter message that this strategy factory uses.
   * This is determined using reflection on the generic type parameter of the interface.
   *
   * @return The {@link Class} that this factory unpacks {@link Any} into.
   */
  default Class<T> getParameterClass() {
    Type genericSuperclass = getClass().getGenericInterfaces()[0];
    ParameterizedType parameterizedType = (ParameterizedType) genericSuperclass;
    Type actualTypeArgument = parameterizedType.getActualTypeArguments()[0];
    return (Class<T>) actualTypeArgument;
  }
}
