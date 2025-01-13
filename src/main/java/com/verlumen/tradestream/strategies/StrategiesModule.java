package com.verlumen.tradestream.strategies;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.TypeLiteral;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.verlumen.tradestream.backtesting.BacktestingModule;
import com.verlumen.tradestream.signals.SignalsModule;

@AutoValue
abstract class StrategiesModule extends AbstractModule {
  static StrategiesModule create(String candleTopic, String signalTopic) {
    return new AutoValue_StrategiesModule(candleTopic, signalTopic);
  }
  
  abstract String candleTopic();
  abstract String signalTopic();

  @Override
  protected void configure() {
    bind(MarketDataConsumer.class).to(MarketDataConsumerImpl.class);
    bind(new TypeLiteral<ImmutableList<StrategyFactory<?>>>() {})
        .toInstance(StrategyFactories.ALL_FACTORIES);
    bind(StrategyManager.class).to(StrategyManagerImpl.class);

    install(BacktestingModule.create());
    install(SignalsModule.create());
    install(new FactoryModuleBuilder()
        .implement(StrategyEngine.class, StrategyEngineImpl.class)
        .build(StrategyEngine.Factory.class));
  }

  @Provides
  StrategyEngine provideStrategyEngine(StrategyEngine.Factory factory) {
    StrategyEngine.Config config = new StrategyEngine.Config(candleTopic(), signalTopic());
    return factory.create(config);
  }
}
