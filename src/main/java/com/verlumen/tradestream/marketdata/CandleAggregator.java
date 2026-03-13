package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Timestamp;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;

/**
 * Aggregates raw trade events into OHLCV candles at a configurable timeframe. Supports multiple
 * asset pairs simultaneously. Emits completed candles via a registered listener.
 */
public class CandleAggregator {

  private final Timeframe timeframe;
  private final Map<String, CandleBuilder> activeCandles = new ConcurrentHashMap<>();
  private final List<Consumer<Candle>> listeners = new ArrayList<>();

  public CandleAggregator(Timeframe timeframe) {
    this.timeframe = timeframe;
  }

  /** Register a listener that will be called when a candle is completed. */
  public void addListener(Consumer<Candle> listener) {
    listeners.add(listener);
  }

  /** Process a raw trade event. Completes and emits any candle whose period has ended. */
  public void onTrade(Trade trade) {
    String pair = trade.getCurrencyPair();
    long tradeMillis = toEpochMillis(trade.getTimestamp());
    long intervalStart = timeframe.alignToInterval(tradeMillis);

    CandleBuilder builder = activeCandles.get(pair);

    if (builder != null && builder.getIntervalStart() != intervalStart) {
      // The trade falls in a new interval — emit the completed candle and gap-fill if needed.
      emitWithGapFill(pair, builder, intervalStart);
      builder = null;
    }

    if (builder == null) {
      builder =
          new CandleBuilder(
              pair,
              intervalStart,
              trade.getPrice(),
              trade.getPrice(),
              trade.getPrice(),
              trade.getPrice(),
              trade.getVolume());
      activeCandles.put(pair, builder);
    } else {
      builder.update(trade.getPrice(), trade.getVolume());
    }
  }

  /**
   * Force-flush all active candles. Useful at shutdown or when you want to get the current
   * in-progress candles.
   */
  public ImmutableList<Candle> flush() {
    ImmutableList.Builder<Candle> flushed = ImmutableList.builder();
    for (Map.Entry<String, CandleBuilder> entry : activeCandles.entrySet()) {
      Candle candle = entry.getValue().build();
      flushed.add(candle);
      emit(candle);
    }
    activeCandles.clear();
    return flushed.build();
  }

  private void emitWithGapFill(String pair, CandleBuilder completedBuilder, long newIntervalStart) {
    Candle completed = completedBuilder.build();
    emit(completed);

    // Gap-fill any empty intervals between the completed candle and the new trade's interval.
    long durationMillis = timeframe.getDuration().toMillis();
    long gapStart = completedBuilder.getIntervalStart() + durationMillis;
    while (gapStart < newIntervalStart) {
      Candle gapCandle = buildGapCandle(pair, gapStart, completed.getClose());
      emit(gapCandle);
      gapStart += durationMillis;
    }
  }

  private Candle buildGapCandle(String pair, long intervalStart, double lastClose) {
    return Candle.newBuilder()
        .setTimestamp(fromEpochMillis(intervalStart))
        .setCurrencyPair(pair)
        .setOpen(lastClose)
        .setHigh(lastClose)
        .setLow(lastClose)
        .setClose(lastClose)
        .setVolume(0)
        .build();
  }

  private void emit(Candle candle) {
    for (Consumer<Candle> listener : listeners) {
      listener.accept(candle);
    }
  }

  private static long toEpochMillis(Timestamp ts) {
    return ts.getSeconds() * 1000 + ts.getNanos() / 1_000_000;
  }

  private static Timestamp fromEpochMillis(long millis) {
    return Timestamp.newBuilder()
        .setSeconds(millis / 1000)
        .setNanos((int) ((millis % 1000) * 1_000_000))
        .build();
  }

  /** Mutable builder for accumulating OHLCV data within a single interval. */
  static class CandleBuilder {
    private final String pair;
    private final long intervalStart;
    private final double open;
    private double high;
    private double low;
    private double close;
    private double volume;

    CandleBuilder(
        String pair,
        long intervalStart,
        double open,
        double high,
        double low,
        double close,
        double volume) {
      this.pair = pair;
      this.intervalStart = intervalStart;
      this.open = open;
      this.high = high;
      this.low = low;
      this.close = close;
      this.volume = volume;
    }

    void update(double price, double tradeVolume) {
      if (price > high) high = price;
      if (price < low) low = price;
      close = price;
      volume += tradeVolume;
    }

    long getIntervalStart() {
      return intervalStart;
    }

    Candle build() {
      return Candle.newBuilder()
          .setTimestamp(
              Timestamp.newBuilder()
                  .setSeconds(intervalStart / 1000)
                  .setNanos((int) ((intervalStart % 1000) * 1_000_000))
                  .build())
          .setCurrencyPair(pair)
          .setOpen(open)
          .setHigh(high)
          .setLow(low)
          .setClose(close)
          .setVolume(volume)
          .build();
    }
  }
}
