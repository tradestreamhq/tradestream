package com.verlumen.tradestream.backtesting;

import static com.google.common.base.Preconditions.checkArgument;

import com.google.common.collect.ImmutableMap;
import com.google.inject.Inject;
import com.verlumen.tradestream.strategies.StrategyType;
import java.io.Serializable;

final class ParamConfigManagerImpl implements ParamConfigManager {
  private final ImmutableMap<StrategyType, ParamConfig> configMap;

  @Inject
  ParamConfigManagerImpl() {
    this.configMap = ImmutableMap.of();
  }

  @Override
  public ParamConfig getParamConfig(StrategyType strategyType) {
    checkArgument(configMap.containsKey(strategyType));
    return configMap.get(strategyType);
  }
}
