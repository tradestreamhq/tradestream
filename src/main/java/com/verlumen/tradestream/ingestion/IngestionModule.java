package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.kafka.KafkaModule;
import com.verlumen.tradestream.kafka.KafkaProperties;
import info.bitrich.xchangestream.core.StreamingExchange;
import java.util.Timer;
import net.sourceforge.argparse4j.inf.Namespace;

@AutoValue
abstract class IngestionModule extends AbstractModule {
  static IngestionModule create(Namespace namespace) {
    String candlePublisherTopic = namespace.getString("candlePublisherTopic");
    String coinMarketCapApiKey = namespace.getString("coinmarketcap.apiKey");
    int topNCryptocurrencies = namespace.getInt("coinmarketcap.topN");
    String exchangeName = namespace.getString("exchangeName");
    long candleIntervalMillis = namespace.getInt("candleIntervalSeconds") * 1000L;
    String runModeName = namespace.getString("runMode").toUpperCase();
    RunMode runMode = RunMode.valueOf(runModeName);
    KafkaProperties kafkaProperties =
        KafkaProperties.createFromKafkaPrefixedProperties(namespace.getAttrs());

    return new AutoValue_IngestionModule(
        candlePublisherTopic,
        coinMarketCapApiKey,
        topNCryptocurrencies,
        exchangeName,
        candleIntervalMillis,
        runMode,
        kafkaProperties
    );
  }

  abstract String candlePublisherTopic();
  abstract String coinMarketCapApiKey();
  abstract int topNCryptocurrencies();
  abstract String exchangeName();
  abstract long candleIntervalMillis();
  abstract RunMode runMode();
  abstract KafkaProperties kafkaProperties();

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

    install(new FactoryModuleBuilder()
        .implement(CandleManager.class, CandleManagerImpl.class)
        .build(CandleManager.Factory.class));

    install(new FactoryModuleBuilder()
        .implement(CandlePublisher.class, CandlePublisherImpl.class)
        .build(CandlePublisher.Factory.class));

    // Install Kafka module using the KafkaProperties we stored
    install(KafkaModule.create(kafkaProperties()));
  }

  @Provides
  CandleManager provideCandleManager(
      CandlePublisher candlePublisher, CandleManager.Factory candleManagerFactory) {
    return candleManagerFactory.create(candleIntervalMillis(), candlePublisher);
  }

  @Provides
  CandlePublisher provideCandlePublisher(CandlePublisher.Factory candlePublisherFactory) {
    return candlePublisherFactory.create(candlePublisherTopic());
  }

  @Provides
  CoinMarketCapConfig provideCoinMarketCapConfig() {
    return CoinMarketCapConfig.create(topNCryptocurrencies(), coinMarketCapApiKey());
  }

  @Provides
  ExchangeStreamingClient provideExchangeStreamingClient(
      ExchangeStreamingClient.Factory exchangeStreamingClientFactory) {
    return exchangeStreamingClientFactory.create(exchangeName());
  }

  @Provides
  RunMode provideRunMode() {
    return runMode();
  }

  @Provides
  TradeProcessor provideTradeProcessor() {
    return TradeProcessor.create(candleIntervalMillis());
  }
}
