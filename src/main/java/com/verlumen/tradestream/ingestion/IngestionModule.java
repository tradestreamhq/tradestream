package com.verlumen.tradestream.ingestion;

import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.AbstractModule;
import com.google.inject.TypeLiteral;
import org.apache.kafka.clients.producer.KafkaProducer;
import info.bitrich.xchangestream.core.StreamingExchange;
import net.sourceforge.argparse4j.inf.Namespace;

import java.util.Properties;

final class IngestionModule extends AbstractModule {
  @Override
  protected void configure() {
    bind(new TypeLiteral<KafkaProducer<String, byte[]>>() {})
        .toProvider(KafkaProducerProvider.class);
    bind(Namespace.class).toProvider(ConfigArguments.create());
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
