package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.TypeLiteral;
import org.apache.kafka.clients.producer.KafkaProducer;
import info.bitrich.xchangestream.core.StreamingExchange;
import net.sourceforge.argparse4j.inf.Namespace;

import java.util.Properties;
import java.util.Timer;

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
    bind(Namespace.class).toProvider(ConfigArguments.create(commandLineArgs()));
    bind(StreamingExchange.class).toProvider(StreamingExchangeProvider.class);

    bind(CurrencyPairSupplier.class).to(CurrencyPairSupplierImpl.class);
    bind(RealTimeDataIngestion.class).to(RealTimeDataIngestionImpl.class);
    bind(ThinMarketTimer.class).to(ThinMarketTimerImpl.class);
    bind(ThinMarketTimerTask.class).to(ThinMarketTimerTaskImpl.class);
    bind(Timer.class).toProvider(Timer::new);

    install(new FactoryModuleBuilder()
        .implement(CandleManager.class, CandleManagerImpl.class)
        .build(CandleManager.Factory.class));    
    install(new FactoryModuleBuilder()
        .implement(CandlePublisher.class, CandlePublisherImpl.class)
        .build(CandlePublisher.Factory.class));
  }

  @Provides
  CandleManager provideCandleManager(Namespace namespace, CandlePublisher candlePublisher, CandleManager.Factory candleMangerFactory) {
    long candleIntervalMillis = namespace.getInt("candleIntervalSeconds") * 1000;
    return candleMangerFactory.create(candleIntervalMillis, candlePublisher);
  }

  @Provides
  CandlePublisher provideCandlePublisher(Namespace namespace, CandlePublisher.Factory candlePublisherFactory) {
    String topic = namespace.getString("candlePublisherTopic");
    return candlePublisherFactory.create(topic);
  }


  @Provides
  ProductSubscription provideProductSubscription() {
    return ProductSubscription
      .create()
      .build();
  }
  
  @Provides
  RunMode provideRunMode(Namespace namespace) {
    String runModeName = namespace.getString("runMode").toUpperCase();
    return RunMode.valueOf(runModeName);
  }

  @Provides
  TradeProcessor provideTradeProcessor(Namespace namespace) {
    long candleIntervalMillis = namespace.getInt("candleIntervalSeconds") * 1000;
    return TradeProcessor.create(candleIntervalMillis);
  }
}
