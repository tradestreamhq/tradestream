package com.verlumen.tradestream.strategies;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.Singleton;
import com.google.inject.TypeLiteral;
import com.verlumen.tradestream.signals.TradeSignalPublisher;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.apache.kafka.clients.consumer.KafkaConsumer;

@AutoValue
abstract class StrategiesModule extends AbstractModule {
  static StrategiesModule create(String candleTopic, String signalTopic) {
    return new AutoValue_StrategiesModule(candleTopic, signalTopic);
  }
  
  abstract String candleTopic();
  abstract String signalTopic();

  @Override
  protected void configure() {
    bind(new TypeLiteral<ImmutableList<StrategyFactory<?>>>() {})
        .toInstance(StrategyFactories.ALL_FACTORIES);
    bind(StrategyManager.class).to(StrategyManagerImpl.class);
    bind(StrategyState.Factory.class).to(StrategyStateFactoryImpl.class);
  }

  @Provides
  TradeSignalPublisher provideTradeSignalPublisher(TradeSignalPublisher.Factory factory) {
    return factory.create(signalTopic());
  }
}
