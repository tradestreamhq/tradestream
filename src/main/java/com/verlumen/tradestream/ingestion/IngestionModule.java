package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.kafka.KafkaModule;
import com.verlumen.tradestream.marketdata.MarketDataModule;
import java.util.Timer;

@AutoValue
abstract class IngestionModule extends AbstractModule {
  static IngestionModule create(IngestionConfig ingestionConfig) {
    return new AutoValue_IngestionModule(ingestionConfig);
  }

  abstract IngestionConfig ingestionConfig();

  @Override
  protected void configure() {
    bind(CurrencyPairSupply.class).toProvider(CurrencyPairSupplyProvider.class);
    bind(ExchangeStreamingClient.Factory.class).to(ExchangeStreamingClientFactory.class);
    bind(HttpClient.class).to(HttpClientImpl.class);
    bind(java.net.http.HttpClient.class).toProvider(java.net.http.HttpClient::newHttpClient);
    bind(HttpURLConnectionFactory.class).to(HttpURLConnectionFactoryImpl.class);
    bind(RealTimeDataIngestion.class).to(RealTimeDataIngestionImpl.class);
    bind(ThinMarketTimer.class).to(ThinMarketTimerImpl.class);
    bind(ThinMarketTimerTask.class).to(ThinMarketTimerTaskImpl.class);
    bind(Timer.class).toProvider(Timer::new);

    install(
        new FactoryModuleBuilder()
            .implement(CandleManager.class, CandleManagerImpl.class)
            .build(CandleManager.Factory.class));

    install(
        new FactoryModuleBuilder()
            .implement(CandlePublisher.class, CandlePublisherImpl.class)
            .build(CandlePublisher.Factory.class));

    install(KafkaModule.create(ingestionConfig().kafkaBootstrapServers()));
    install(MarketDataModule.create());
  }

  @Provides
  CandleManager provideCandleManager(
      CandlePublisher candlePublisher, CandleManager.Factory candleManagerFactory) {
    return candleManagerFactory.create(
        ingestionConfig().candleIntervalMillis(), candlePublisher);
  }

  @Provides
  CandlePublisher provideCandlePublisher(CandlePublisher.Factory candlePublisherFactory) {
    return candlePublisherFactory.create(ingestionConfig().candlePublisherTopic());
  }

  @Provides
  CoinMarketCapConfig provideCoinMarketCapConfig() {
    return CoinMarketCapConfig.create(
        ingestionConfig().topCryptocurrencyCount(), ingestionConfig().coinMarketCapApiKey());
  }

  @Provides
  ExchangeStreamingClient provideExchangeStreamingClient(
      ExchangeStreamingClient.Factory exchangeStreamingClientFactory) {
    return exchangeStreamingClientFactory.create(ingestionConfig().exchangeName());
  }

  @Provides
  RunMode provideRunMode() {
    return ingestionConfig().runMode();
  }

  @Provides
  TradeProcessor provideTradeProcessor() {
    return TradeProcessor.create(ingestionConfig().candleIntervalMillis());
  }
}
