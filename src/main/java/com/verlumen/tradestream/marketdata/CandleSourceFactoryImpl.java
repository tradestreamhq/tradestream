package com.verlumen.tradestream.marketdata;

import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.execution.RunMode;
import org.joda.time.Duration;

/**
 * Implementation of CandleSourceFactory that creates appropriate CandleSource instances
 * based on the runtime configuration.
 */
public class CandleSourceFactoryImpl implements CandleSourceFactory {
  private final Provider<TradeBackedCandleSource> tradeBackedCandleSource;
  private final TiingoCryptoCandleSource.Factory tiingoCryptoCandleSourceFactory;

  @Inject
  public CandleSourceFactoryImpl(
      Provider<TradeBackedCandleSource> tradeBackedCandleSource,
      TiingoCryptoCandleSource.Factory tiingoCryptoCandleSourceFactory) {
    this.tradeBackedCandleSource = tradeBackedCandleSource;
    this.tiingoCryptoCandleSourceFactory = tiingoCryptoCandleSourceFactory;
  }

  @Override
  public CandleSource create(RunMode runMode, Duration granularity, String tiingoApiKey) {
    switch (runMode) {
      case DRY:
        return tradeBackedCandleSource.get();
      case WET:
        return tiingoCryptoCandleSourceFactory.create(granularity, tiingoApiKey);
      default:
        throw new UnsupportedOperationException("Unsupported RunMode: " + runMode);
    }
  }
} 