package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.TypeLiteral;

final class StrategiesModule extends AbstractModule {
  static StrategiesModule create() {
    return new StrategiesModule();
  }
  
  @Override
  protected void configure() {
    bind(MarketDataConsumer.class).to(MarketDataConsumerImpl.class);
    bind(new TypeLiteral<ImmutableList<StrategyFactory<?>>>() {})
        .toInstance(StrategyFactories.ALL_FACTORIES);
  }
}
