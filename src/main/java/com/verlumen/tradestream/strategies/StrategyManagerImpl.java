package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import com.google.inject.Inject;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.Message;
import org.ta4j.core.Strategy;

public class StrategyManagerImpl {
  private final Config config;

  @Inject
  StrategyManagerImpl(Config config) {
    this.config = config;
  }

  @Override
  public Strategy createStrategy(Any strategyParameters, StrategyType strategyType) throws InvalidProtocolBufferException {      
    StrategyFactory<?> factory = config.factoryMap().get(strategyType);
    if (factory == null) {
        throw new IllegalArgumentException("Unsupported strategy type: " + strategyType);
    }

    Object params = strategyParameters.unpack(factory.getParameterClass());
    return factory.createStrategy(params);
  }

  private <T extends Message> Strategy createStrategy(Any strategyParameters, StrategyFactory factory, Class<T> parameterClass) throws InvalidProtocolBufferException {
    T params = strategyParameters.unpack(factory.getParameterClass());
    return factory.createStrategy(params);
  }
}
