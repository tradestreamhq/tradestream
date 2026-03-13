package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/** Thread-safe in-memory implementation of {@link CandleStore}. */
public class InMemoryCandleStore implements CandleStore {

  // Key: "pair|timeframe_label"
  private final Map<String, List<Candle>> store = new ConcurrentHashMap<>();

  @Override
  public void store(Candle candle, Timeframe timeframe) {
    String key = makeKey(candle.getCurrencyPair(), timeframe);
    store.computeIfAbsent(key, k -> Collections.synchronizedList(new ArrayList<>())).add(candle);
  }

  @Override
  public ImmutableList<Candle> query(
      String currencyPair, Timeframe timeframe, long startMillis, long endMillis) {
    String key = makeKey(currencyPair, timeframe);
    List<Candle> candles = store.getOrDefault(key, Collections.emptyList());

    ImmutableList.Builder<Candle> result = ImmutableList.builder();
    synchronized (candles) {
      for (Candle c : candles) {
        long ts = toEpochMillis(c.getTimestamp());
        if (ts >= startMillis && ts <= endMillis) {
          result.add(c);
        }
      }
    }
    return result.build();
  }

  @Override
  public ImmutableList<Candle> latest(String currencyPair, Timeframe timeframe, int count) {
    String key = makeKey(currencyPair, timeframe);
    List<Candle> candles = store.getOrDefault(key, Collections.emptyList());

    synchronized (candles) {
      int size = candles.size();
      int fromIndex = Math.max(0, size - count);
      // Return in reverse order (most recent first).
      List<Candle> subList = new ArrayList<>(candles.subList(fromIndex, size));
      Collections.reverse(subList);
      return ImmutableList.copyOf(subList);
    }
  }

  private static String makeKey(String currencyPair, Timeframe timeframe) {
    return currencyPair + "|" + timeframe.getLabel();
  }

  private static long toEpochMillis(com.google.protobuf.Timestamp ts) {
    return ts.getSeconds() * 1000 + ts.getNanos() / 1_000_000;
  }
}
