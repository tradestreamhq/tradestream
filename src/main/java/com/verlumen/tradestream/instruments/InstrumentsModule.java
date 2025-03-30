package com.verlumen.tradestream.instruments;

import com.google.auto.value.AutoValue;
import com.google.common.base.Suppliers;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

@AutoValue
public abstract class InstrumentsModule extends AbstractModule {
  public static InstrumentsModule create(String coinMarketCapApiKey, int topCryptocurrencyCount) {
    return new AutoValue_InstrumentsModule(coinMarketCapApiKey, topCryptocurrencyCount);
  }

  private static final long ONE = 1L;

  abstract String coinMarketCapApiKey();
  abstract int topCryptocurrencyCount();

  @Provides
  CoinMarketCapConfig provideCoinMarketCapConfig() {
    return CoinMarketCapConfig.create(
        topCryptocurrencyCount(), coinMarketCapApiKey());
  }

  @Provides
  @Singleton
  Supplier<ImmutableList<CurrencyPair>> provideCurrencyPairSupplier(
    CurrencyPairSupplyProvider provider) {
    return Suppliers.memoizeWithExpiration(provider.get(), ONE, TimeUnit.DAYS);
  }
}
