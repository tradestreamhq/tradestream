package com.verlumen.tradestream.ingestion;

import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.AbstractModule;
import com.google.inject.TypeLiteral;

final class IngestionModule extends AbstractModule {
  @Override
  protected void configure() {
    bind(new TypeLiteral<KafkaProducer<String, byte[]>>() {}).toProvider();
    bind(KafkaProducer.class).toProvider(KafkaProducerProvider.class);
    bind(MarketDataIngestion.class).to(RealTimeDataIngestion.class);

    install(new FactoryModuleBuilder()
     .implement(CandlePublisher.class, CandlePublisherImpl.class)
     .build(CandlePublisher.Factory.class));
  }
}
