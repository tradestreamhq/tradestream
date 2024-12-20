package com.verlumen.tradestream.strategies;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.Strategy;

interface StrategyManager {
  Strategy createStrategy(StrategyType strategyType, Any strategyParameters) throws InvalidProtocolBufferException;
}
