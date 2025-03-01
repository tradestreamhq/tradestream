package com.verlumen.tradestream.backtesting.params;

import com.verlumen.tradestream.strategies.StrategyType;
import java.io.Serializable;

public interface ParamConfigManager extends Serializable {
  ParamConfig getParamConfig(StrategyType strategyType);
}
