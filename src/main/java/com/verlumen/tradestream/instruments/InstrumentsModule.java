package com.verlumen.tradestream.instruments;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;

@AutoValue
abstract class InstrumentsModule extends AbstractModule {
  static InstrumentsModule create(String coinMarketCapApiKey, int topCryptocurrencyCount) {
    return new AutoValue_InstrumentsModule(coinMarketCapApiKey, topCryptocurrencyCount);
  }

  abstract String coinMarketCapApiKey();
  abstract int topCryptocurrencyCount();

  @Provides
  CoinMarketCapConfig provideCoinMarketCapConfig() {
    return CoinMarketCapConfig.create(
        topCryptocurrencyCount(), coinMarketCapApiKey());
  }
}
