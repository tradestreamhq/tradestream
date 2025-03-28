package com.verlumen.tradestream.instruments;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;

@AutoValue
abstract class InstrumentsModule extends AbstractModule {
  @Provides
  CoinMarketCapConfig provideCoinMarketCapConfig() {
    return CoinMarketCapConfig.create(
        ingestionConfig().topCryptocurrencyCount(), ingestionConfig().coinMarketCapApiKey());
  }
}
