package com.verlumen.tradestream.marketdata;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Timestamp;
import java.util.ArrayList;
import java.util.List;
import org.junit.Before;
import org.junit.Test;

public class CandleAggregatorTest {

  private CandleAggregator aggregator;
  private List<Candle> emittedCandles;

  @Before
  public void setUp() {
    aggregator = new CandleAggregator(Timeframe.ONE_MINUTE);
    emittedCandles = new ArrayList<>();
    aggregator.addListener(emittedCandles::add);
  }

  @Test
  public void singleTradeProducesNoCandleUntilNextInterval() {
    aggregator.onTrade(trade("BTC/USD", 100.0, 1.0, 60_000L));
    assertThat(emittedCandles).isEmpty();
  }

  @Test
  public void tradeInNextIntervalEmitsCompletedCandle() {
    aggregator.onTrade(trade("BTC/USD", 100.0, 1.0, 60_000L));
    aggregator.onTrade(trade("BTC/USD", 105.0, 2.0, 120_000L));

    assertThat(emittedCandles).hasSize(1);
    Candle candle = emittedCandles.get(0);
    assertThat(candle.getCurrencyPair()).isEqualTo("BTC/USD");
    assertThat(candle.getOpen()).isEqualTo(100.0);
    assertThat(candle.getHigh()).isEqualTo(100.0);
    assertThat(candle.getLow()).isEqualTo(100.0);
    assertThat(candle.getClose()).isEqualTo(100.0);
    assertThat(candle.getVolume()).isEqualTo(1.0);
  }

  @Test
  public void multipleTradesInSameIntervalAggregateCorrectly() {
    aggregator.onTrade(trade("BTC/USD", 100.0, 1.0, 60_000L));
    aggregator.onTrade(trade("BTC/USD", 110.0, 2.0, 70_000L));
    aggregator.onTrade(trade("BTC/USD", 90.0, 3.0, 80_000L));
    aggregator.onTrade(trade("BTC/USD", 105.0, 4.0, 90_000L));

    // Force emit by sending a trade in the next interval.
    aggregator.onTrade(trade("BTC/USD", 200.0, 1.0, 120_000L));

    assertThat(emittedCandles).hasSize(1);
    Candle candle = emittedCandles.get(0);
    assertThat(candle.getOpen()).isEqualTo(100.0);
    assertThat(candle.getHigh()).isEqualTo(110.0);
    assertThat(candle.getLow()).isEqualTo(90.0);
    assertThat(candle.getClose()).isEqualTo(105.0);
    assertThat(candle.getVolume()).isEqualTo(10.0);
  }

  @Test
  public void gapFillingCreatesEmptyCandles() {
    // Trade at minute 1 (60s).
    aggregator.onTrade(trade("BTC/USD", 100.0, 1.0, 60_000L));
    // Trade at minute 4 (240s) — skips minutes 2 and 3.
    aggregator.onTrade(trade("BTC/USD", 200.0, 1.0, 240_000L));

    // Should emit: minute 1 candle + 2 gap-fill candles (minutes 2 and 3).
    assertThat(emittedCandles).hasSize(3);

    // Gap candles have OHLC = last close price, volume = 0.
    Candle gap1 = emittedCandles.get(1);
    assertThat(gap1.getOpen()).isEqualTo(100.0);
    assertThat(gap1.getVolume()).isEqualTo(0.0);

    Candle gap2 = emittedCandles.get(2);
    assertThat(gap2.getOpen()).isEqualTo(100.0);
    assertThat(gap2.getVolume()).isEqualTo(0.0);
  }

  @Test
  public void multiplePairsAreTrackedIndependently() {
    aggregator.onTrade(trade("BTC/USD", 100.0, 1.0, 60_000L));
    aggregator.onTrade(trade("ETH/USD", 50.0, 10.0, 60_000L));

    // Advance both pairs to next interval.
    aggregator.onTrade(trade("BTC/USD", 110.0, 1.0, 120_000L));
    aggregator.onTrade(trade("ETH/USD", 55.0, 5.0, 120_000L));

    assertThat(emittedCandles).hasSize(2);
    assertThat(emittedCandles.get(0).getCurrencyPair()).isEqualTo("BTC/USD");
    assertThat(emittedCandles.get(0).getOpen()).isEqualTo(100.0);
    assertThat(emittedCandles.get(1).getCurrencyPair()).isEqualTo("ETH/USD");
    assertThat(emittedCandles.get(1).getOpen()).isEqualTo(50.0);
  }

  @Test
  public void flushEmitsAllActiveCandles() {
    aggregator.onTrade(trade("BTC/USD", 100.0, 1.0, 60_000L));
    aggregator.onTrade(trade("ETH/USD", 50.0, 10.0, 60_000L));

    ImmutableList<Candle> flushed = aggregator.flush();
    assertThat(flushed).hasSize(2);
    assertThat(emittedCandles).hasSize(2);
  }

  @Test
  public void fiveMinuteTimeframe() {
    CandleAggregator fiveMin = new CandleAggregator(Timeframe.FIVE_MINUTES);
    List<Candle> candles = new ArrayList<>();
    fiveMin.addListener(candles::add);

    // Trades within same 5-minute window (0-299s).
    fiveMin.onTrade(trade("BTC/USD", 100.0, 1.0, 0L));
    fiveMin.onTrade(trade("BTC/USD", 110.0, 2.0, 60_000L));
    fiveMin.onTrade(trade("BTC/USD", 95.0, 3.0, 240_000L));
    assertThat(candles).isEmpty();

    // Trade in next 5-minute window (300s).
    fiveMin.onTrade(trade("BTC/USD", 120.0, 1.0, 300_000L));
    assertThat(candles).hasSize(1);
    assertThat(candles.get(0).getOpen()).isEqualTo(100.0);
    assertThat(candles.get(0).getHigh()).isEqualTo(110.0);
    assertThat(candles.get(0).getLow()).isEqualTo(95.0);
    assertThat(candles.get(0).getClose()).isEqualTo(95.0);
    assertThat(candles.get(0).getVolume()).isEqualTo(6.0);
  }

  private static Trade trade(String pair, double price, double volume, long epochMillis) {
    return Trade.newBuilder()
        .setCurrencyPair(pair)
        .setPrice(price)
        .setVolume(volume)
        .setTimestamp(
            Timestamp.newBuilder()
                .setSeconds(epochMillis / 1000)
                .setNanos((int) ((epochMillis % 1000) * 1_000_000))
                .build())
        .build();
  }
}
