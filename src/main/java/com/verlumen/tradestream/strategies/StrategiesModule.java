package com.verlumen.tradestream.strategies;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.google.inject.TypeLiteral;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.verlumen.tradestream.backtesting.BacktestingModule;
import com.verlumen.tradestream.signals.SignalsModule;
import com.verlumen.tradestream.signals.TradeSignalPublisher;
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
    bind(CandleBuffer.class).to(CandleBufferImpl.class);
    bind(new TypeLiteral<KafkaConsumer<byte[], byte[]>>() {})
        .toProvider(KafkaConsumerProvider.class)
        .in(Singleton.class);
    bind(MarketDataConsumer.class).to(MarketDataConsumerImpl.class);
    bind(StrategyEngine.class).to(StrategyEngineImpl.class);
    bind(new TypeLiteral<ImmutableList<StrategyFactory<?>>>() {})
        .toInstance(StrategyFactories.ALL_FACTORIES);
    bind(StrategyManager.class).to(StrategyManagerImpl.class);

    install(BacktestingModule.create());
    install(SignalsModule.create());
  }

  @Provides
  TradeSignalPublisher provideTradeSignalPublisher(TradeSignalPublisher.Factory factory) {
    return factory.create(signalTopic());
  }
}
