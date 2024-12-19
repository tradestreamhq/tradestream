package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.Message;
import org.ta4j.core.Strategy;
import java.util.Map;

interface StrategyManager {
  Strategy createStrategy(StrategyType strategyType, Any strategyParameters) throws InvalidProtocolBufferException;
  
  @AutoValue
  abstract class Config {
    abstract ImmutableMap<StrategyType, StrategyFactory> factoryMap();
  }
}
