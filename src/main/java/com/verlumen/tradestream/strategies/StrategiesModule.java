package com.verlumen.tradestream.strategies;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;

@AutoValue
abstract class StrategiesModule extends AbstractModule {
  static StrategiesModule create() {
    return new StrategiesModule();
  }
  
  @Override
  protected void configure() {
    bind(MarketDataConsumer.class).to(MarketDataConsumerImpl.class);
  }
}
