package com.verlumen.tradestream.instruments;

import com.google.auto.value.AutoValue;
import com.google.common.base.Suppliers;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;

@AutoValue
public abstract class InstrumentsModule extends AbstractModule {
  public static InstrumentsModule create(String coinMarketCapApiKey, int topCryptocurrencyCount) {
    return new AutoValue_InstrumentsModule(coinMarketCapApiKey, topCryptocurrencyCount);
  }
  private static final long ONE = 1L;

  abstract String coinMarketCapApiKey();
  abstract int topCryptocurrencyCount();

  @Override
  protected void configure() {
    bind(CurrencyPairSupply.class).toProvider(CurrencyPairSupplyProvider.class);
  }

  @Provides
  CoinMarketCapConfig provideCoinMarketCapConfig() {
    return CoinMarketCapConfig.create(
        topCryptocurrencyCount(), coinMarketCapApiKey());
  }

  @Provides
  Supplier<CurrencyPair> provideCurrencyPairSupply(CurrencyPairSupplyProvider provider) {
    return Suppliers.memoizeWithExpiration(provider.get(), ONE, TimeUnit.Minutes);
  }
}
