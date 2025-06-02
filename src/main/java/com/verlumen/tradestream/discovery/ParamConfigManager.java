package com.verlumen.tradestream.discovery;

import com.verlumen.tradestream.strategies.StrategyType;
import java.io.Serializable;

public interface ParamConfigManager extends Serializable {
  ParamConfig getParamConfig(StrategyType strategyType);
}
