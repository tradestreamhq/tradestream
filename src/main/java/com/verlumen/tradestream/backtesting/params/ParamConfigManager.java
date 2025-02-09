package com.verlumen.tradestream.backtesting.params;

import com.verlumen.tradestream.strategies.StrategyType;

public interface ParamConfigManager {
  ParamConfig getParamConfig(StrategyType strategyType);
}
