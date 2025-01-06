package com.verlumen.tradestream.strategies;

import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.TypeLiteral;
import com.verlumen.tradestream.backtesting.BacktestingModule;
import com.verlumen.tradestream.signals.SignalsModule;

final class StrategiesModule extends AbstractModule {
  static StrategiesModule create() {
    return new StrategiesModule();
  }
  
  @Override
  protected void configure() {
    bind(MarketDataConsumer.class).to(MarketDataConsumerImpl.class);
    bind(StrategyEngine.class).to(StrategyEngineImpl.class);
    bind(new TypeLiteral<ImmutableList<StrategyFactory<?>>>() {})
        .toInstance(StrategyFactories.ALL_FACTORIES);
    bind(StrategyManager.class).to(StrategyManagerImpl.class);

    install(BacktestingModule.create());
    install(SignalsModule.create());
  }
}
