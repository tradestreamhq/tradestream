package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.AbstractModule;
import com.google.inject.TypeLiteral;
import org.apache.kafka.clients.producer.KafkaProducer;
import info.bitrich.xchangestream.core.StreamingExchange;

import java.util.Properties;

@AutoValue
abstract class IngestionModule extends AbstractModule {
  static IngestionModule create(String[] commandLineArgs) {
    return new AutoValue_IngestionModule(ImmutableList.copyOf(commandLineArgs));
  }

  abstract ImmutableList<String> commandLineArgs();
  
  @Override
  protected void configure() {
    bind(new TypeLiteral<KafkaProducer<String, byte[]>>() {})
        .toProvider(KafkaProducerProvider.class);
    bind(Properties.class).toProvider(PropertiesProvider.class);
    bind(StreamingExchange.class).toProvider(StreamingExchangeProvider.class);

    bind(MarketDataIngestion.class).to(RealTimeDataIngestion.class);

    install(new FactoryModuleBuilder()
        .implement(CandleManager.class, CandleManagerImpl.class)
        .build(CandleManager.Factory.class));    
    install(new FactoryModuleBuilder()
        .implement(CandlePublisher.class, CandlePublisherImpl.class)
        .build(CandlePublisher.Factory.class));
  }
}
