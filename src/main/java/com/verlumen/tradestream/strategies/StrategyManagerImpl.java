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
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.Strategy;

final class StrategyManagerImpl {
  private final Config config;

  @Inject
  StrategyManagerImpl(Config config) {
    this.config = config;
  }

  @Override
  public Strategy createStrategy(Any parameters, StrategyType strategyType) throws InvalidProtocolBufferException {      
    StrategyFactory<?> factory = config.factoryMap().get(strategyType);
    if (factory == null) {
        throw new IllegalArgumentException("Unsupported strategy type: " + strategyType);
    }

    return factory.createStrategy(parameters.unpack(factory.getParameterClass()));
  }

  @AutoValue
  abstract class Config {
    static Config create(ImmutableList<StrategyFactory> factories) {
      ImmutableMap<StrategyType, StrategyFactory> factoryMap = 
        ImmutableMap.copyOf(
          BiStream.from(factories, StrategyFactory::getStrategyType, identity())
          .toMap());
      return new AutoValue_StrategyManagerImpl_Config();
    }
    
    abstract ImmutableMap<StrategyType, StrategyFactory> factoryMap();
  }
}
