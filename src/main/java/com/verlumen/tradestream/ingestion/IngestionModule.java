package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.http.HttpModule;
import com.verlumen.tradestream.kafka.KafkaModule;
import com.verlumen.tradestream.marketdata.MarketDataModule;

@AutoValue
abstract class IngestionModule extends AbstractModule {
  static IngestionModule create(IngestionConfig ingestionConfig) {
    return new AutoValue_IngestionModule(ingestionConfig);
  }

  abstract IngestionConfig ingestionConfig();

  @Override
  protected void configure() {
    bind(CurrencyPairSupply.class).toProvider(CurrencyPairSupplyProvider.class);
    bind(RealTimeDataIngestion.class).to(RealTimeDataIngestionImpl.class);

    install(HttpModule.create());
    install(KafkaModule.create(ingestionConfig().kafkaBootstrapServers()));
    install(MarketDataModule.create(ingestionConfig().tradeTopic()));
  }

  @Provides
  CoinMarketCapConfig provideCoinMarketCapConfig() {
    return CoinMarketCapConfig.create(
        ingestionConfig().topCryptocurrencyCount(), ingestionConfig().coinMarketCapApiKey());
  }

  @Provides
  RunMode provideRunMode() {
    return ingestionConfig().runMode();
  }
}
