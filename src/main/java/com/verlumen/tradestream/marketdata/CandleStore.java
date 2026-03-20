package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;

/** Interface for persisting and querying aggregated candles. */
public interface CandleStore {

  /** Persist a single candle. */
  void store(Candle candle, Timeframe timeframe);

  /** Query candles for a pair and timeframe within a time range (epoch millis, inclusive). */
  ImmutableList<Candle> query(
      String currencyPair, Timeframe timeframe, long startMillis, long endMillis);

  /** Get the latest N candles for a pair and timeframe, ordered most recent first. */
  ImmutableList<Candle> latest(String currencyPair, Timeframe timeframe, int count);
}
