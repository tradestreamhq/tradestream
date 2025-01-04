package com.verlumen.tradestream.strategies;

import static java.util.function.Function.identity;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import com.google.inject.Inject;
import com.google.mu.util.stream.BiStream;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

final class StrategyManagerImpl implements StrategyManager {
  private final ImmutableMap<StrategyType, StrategyFactory<?>> factoryMap;

  @Inject
  StrategyManagerImpl(ImmutableList<StrategyFactory<?> factories) {
    this.factoryMap =
        BiStream.from(factories, StrategyFactory::getStrategyType, identity())
            .collect(ImmutableMap::toImmutableMap);
  }

  @Override
  public Strategy createStrategy(BarSeries barSeries, StrategyType strategyType, Any parameters)
      throws InvalidProtocolBufferException {
    StrategyFactory<?> factory = config.factoryMap().get(strategyType);
    if (factory == null) {
      throw new IllegalArgumentException("Unsupported strategy type: " + strategyType);
    }

    return factory.createStrategy(barSeries, parameters);
  }
}
