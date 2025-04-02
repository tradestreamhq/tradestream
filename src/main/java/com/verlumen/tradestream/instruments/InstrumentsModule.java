package com.verlumen.tradestream.instruments;

import com.google.auto.value.AutoValue;
import com.google.common.base.Suppliers;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

@AutoValue
public abstract class InstrumentsModule extends AbstractModule {
  public static InstrumentsModule create(String coinMarketCapApiKey, int topCryptocurrencyCount) {
    return new AutoValue_InstrumentsModule(coinMarketCapApiKey, topCryptocurrencyCount);
  }

  private static final Duration INSTRUMENT_REFRESH_INTERVAL = Duration.ofDays(1);

  abstract String coinMarketCapApiKey();
  abstract int topCryptocurrencyCount();

  @Provides
  CoinMarketCapConfig provideCoinMarketCapConfig() {
    return CoinMarketCapConfig.create(topCryptocurrencyCount(), coinMarketCapApiKey());
  }

  @Provides
  @Singleton
  Supplier<List<CurrencyPair>> provideCurrencyPairSupply(CurrencyPairSupplier supplier) {
    return Suppliers.memoizeWithExpiration(
      supplier::get,
      INSTRUMENT_REFRESH_INTERVAL.toMillis(),
      TimeUnit.MILLISECONDS);
  }
}
