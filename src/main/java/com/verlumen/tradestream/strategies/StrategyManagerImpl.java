package com.verlumen.tradestream.strategies;

import static java.util.function.Function.identity;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import com.google.inject.Inject;
import com.google.mu.util.stream.BiStream;

final class StrategyManagerImpl implements StrategyManager {
  private final ImmutableMap<StrategyType, StrategyFactory<?>> factoryMap;

  @Inject
  StrategyManagerImpl(ImmutableList<StrategyFactory<?>> factories) {
    this.factoryMap =
        BiStream.from(factories, StrategyFactory::getStrategyType, identity())
            .collect(ImmutableMap::toImmutableMap);
  }

  @Override
  public StrategyFactory<?> getStrategyFactory(StrategyType strategyType) {
    StrategyFactory<?> factory = factoryMap.get(strategyType);
    if (factory == null) {
      throw new IllegalArgumentException("Unsupported strategy type: " + strategyType);
    }

    return factory;
  }

  @Override
  public ImmutableList<StrategyType> getStrategyTypes() {
    return ImmutableList.copyOf(factoryMap.keySet());
  }
}
