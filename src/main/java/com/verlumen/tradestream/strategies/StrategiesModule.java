package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.TypeLiteral;

public class StrategiesModule extends AbstractModule {
  public static StrategiesModule create() {
    return new StrategiesModule();
  }

  @Override
  protected void configure() {
    bind(new TypeLiteral<ImmutableList<StrategyFactory<?>>>() {})
        .toInstance(StrategyFactories.ALL_FACTORIES);
    bind(StrategyManager.class).to(StrategyManagerImpl.class);
    bind(StrategyState.Factory.class).to(StrategyStateFactoryImpl.class);
  }

  private StrategiesModule() {}
}
