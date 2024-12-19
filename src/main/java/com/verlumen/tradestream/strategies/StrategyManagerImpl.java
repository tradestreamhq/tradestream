package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.Message;
import org.ta4j.core.Strategy;
import java.util.Map;

public class StrategyManagerImpl {
  private final ImmutableMap<StrategyType, StrategyFactory<?>> strategyFactories;

  @Inject
  StrategyManager(ImmutableList<StrategyFactory<? extends Message>> strategyFactories) {
    ImmutableMap.Builder<StrategyType, StrategyFactory<?>> builder = ImmutableMap.builder();
    for (StrategyFactory<?> factory : strategyFactories) {
      builder.put(factory.getStrategyType(), factory);
    }
    this.strategyFactories = builder.build();
  }


   public  Strategy createStrategy(StrategyType strategyType, Any strategyParameters) throws InvalidProtocolBufferException {

        StrategyFactory<?> factory = strategyFactories.get(strategyType);
        if (factory == null) {
            throw new IllegalArgumentException("Unsupported strategy type: " + strategyType);
        }
          Object params = strategyParameters.unpack(factory.getParameterClass());
        return factory.createStrategy(params);
    }
}
