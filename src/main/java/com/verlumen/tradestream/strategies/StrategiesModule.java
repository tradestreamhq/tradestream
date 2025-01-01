package com.verlumen.tradestream.strategies;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;

@AutoValue
abstract class StrategiesModule extends AbstractModule {
  static StrategiesModule create(String[] commandLineArgs) {
    return new AutoValue_StrategiesModule(ImmutableList.copyOf(commandLineArgs));
  }

  abstract ImmutableList<String> commandLineArgs();
  
  @Override
  protected void configure() {
    bind(MarketDataConsumer.class).to(MarketDataConsumerImpl.class);
    bind(StrategyManager.class).to(StrategyManagerImpl.class);
  }
}
