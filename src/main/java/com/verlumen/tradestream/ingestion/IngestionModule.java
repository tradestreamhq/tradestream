package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.google.inject.TypeLiteral;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.kafka.KafkaModule;
import java.util.Properties;
import java.util.Timer;
import info.bitrich.xchangestream.core.StreamingExchange;
import net.sourceforge.argparse4j.inf.Namespace;

@AutoValue
abstract class IngestionModule extends AbstractModule {
  static IngestionModule create(Namespace namespace) {
    return new AutoValue_IngestionModule(ImmutableList.copyOf(commandLineArgs));
  }

  abstract Namespace namespace();
  
  @Override
  protected void configure() {
    bind(Namespace.class).toProvider(this::namespace);
    bind(CurrencyPairSupply.class).toProvider(CurrencyPairSupplyProvider.class);
    bind(ExchangeStreamingClient.Factory.class).to(ExchangeStreamingClientFactory.class);
    bind(HttpClient.class).to(HttpClientImpl.class);
    bind(java.net.http.HttpClient.class).toProvider(java.net.http.HttpClient::newHttpClient);
    bind(HttpURLConnectionFactory.class).to(HttpURLConnectionFactoryImpl.class);
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
    install(KafkaModule.create());
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
  CoinMarketCapConfig provideCoinMarketCapConfig(Namespace namespace) {
    String apiKey = namespace.getString("coinmarketcap.apiKey");
    int topN = namespace.getInt("coinmarketcap.topN");
    return CoinMarketCapConfig.create(topN, apiKey);    
  }

  @Provides
  ExchangeStreamingClient provideExchangeStreamingClient(Namespace namespace, ExchangeStreamingClient.Factory exchangeStreamingClientFactory) {
    return exchangeStreamingClientFactory.create(namespace.getString("exchangeName"));
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
