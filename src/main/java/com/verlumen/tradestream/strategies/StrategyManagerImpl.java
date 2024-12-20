package com.verlumen.tradestream.strategies;

import static java.util.function.Function.identity;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import com.google.inject.Inject;
import com.google.mu.util.stream.BiStream;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.Message;
import org.ta4j.core.Strategy;

final class StrategyManagerImpl implements StrategyManager {
  private final Config config;

  @Inject
  StrategyManagerImpl(Config config) {
    this.config = config;
  }

  @Override
  public Strategy createStrategy(StrategyType strategyType, Any parameters)
      throws InvalidProtocolBufferException {
    StrategyFactory<?> factory = config.factoryMap().get(strategyType);
    if (factory == null) {
      throw new IllegalArgumentException("Unsupported strategy type: " + strategyType);
    }
  
    // The factory returns a parameter class with a known Message subtype.
    Class<? extends Message> parameterClass = factory.getParameterClass();
  
    // Cast the parameter class to Message, since we know it's safe from how we build the map.
    @SuppressWarnings("unchecked")
    Class<Message> castedParameterClass = (Class<Message>) parameterClass;
  
    // Unpack the parameters using the casted parameter class.
    Message paramMessage = parameters.unpack(castedParameterClass);
  
    // Cast the factory to a StrategyFactory<Message> so createStrategy can accept paramMessage.
    @SuppressWarnings("unchecked")
    StrategyFactory<Message> castedFactory = (StrategyFactory<Message>) factory;
  
    // Now call createStrategy with the correctly typed message.
    return castedFactory.createStrategy(paramMessage);
  }


  @AutoValue
  abstract static class Config {
    static Config create(ImmutableList<StrategyFactory<?>> factories) {
      ImmutableMap<StrategyType, StrategyFactory<?>> factoryMap =
          BiStream.from(factories, StrategyFactory::getStrategyType, identity())
              .collect(ImmutableMap::toImmutableMap);
      return new AutoValue_StrategyManagerImpl_Config(factoryMap);
    }

    abstract ImmutableMap<StrategyType, StrategyFactory<?>> factoryMap();
  }
}
