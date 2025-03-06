package com.verlumen.tradestream.backtesting;

import com.verlumen.tradestream.backtesting.params.ParamConfig;
import com.verlumen.tradestream.strategies.StrategyType;
import java.io.Serializable;

public interface ParamConfigManager extends Serializable {
  ParamConfig getParamConfig(StrategyType strategyType);
}
