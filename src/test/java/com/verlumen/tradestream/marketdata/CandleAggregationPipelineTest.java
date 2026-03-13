package com.verlumen.tradestream.marketdata;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Timestamp;
import org.junit.Before;
import org.junit.Test;

public class CandleAggregationPipelineTest {

  private InMemoryCandleStore store;
  private CandleAggregationPipeline pipeline;

  @Before
  public void setUp() {
    store = new InMemoryCandleStore();
    pipeline =
        new CandleAggregationPipeline(
            store, ImmutableList.of(Timeframe.ONE_MINUTE, Timeframe.FIVE_MINUTES));
  }

  @Test
  public void tradesAreAggregatedIntoMultipleTimeframes() {
    // Send trades spanning two 1-minute intervals within the same 5-minute interval.
    pipeline.onTrade(trade("BTC/USD", 100.0, 1.0, 0L));
    pipeline.onTrade(trade("BTC/USD", 110.0, 2.0, 30_000L));

    // Next 1-minute interval triggers 1m candle emission.
    pipeline.onTrade(trade("BTC/USD", 120.0, 3.0, 60_000L));

    // 1m candle should be stored.
    ImmutableList<Candle> oneMinCandles = store.query("BTC/USD", Timeframe.ONE_MINUTE, 0, 60_000L);
    assertThat(oneMinCandles).hasSize(1);
    assertThat(oneMinCandles.get(0).getOpen()).isEqualTo(100.0);
    assertThat(oneMinCandles.get(0).getHigh()).isEqualTo(110.0);
    assertThat(oneMinCandles.get(0).getVolume()).isEqualTo(3.0);

    // 5m candle should not yet be stored (still in same interval).
    ImmutableList<Candle> fiveMinCandles =
        store.query("BTC/USD", Timeframe.FIVE_MINUTES, 0, 300_000L);
    assertThat(fiveMinCandles).isEmpty();
  }

  @Test
  public void flushPersistsInProgressCandles() {
    pipeline.onTrade(trade("BTC/USD", 100.0, 1.0, 0L));
    pipeline.flush();

    ImmutableList<Candle> oneMinCandles = store.query("BTC/USD", Timeframe.ONE_MINUTE, 0, 60_000L);
    assertThat(oneMinCandles).hasSize(1);

    ImmutableList<Candle> fiveMinCandles =
        store.query("BTC/USD", Timeframe.FIVE_MINUTES, 0, 300_000L);
    assertThat(fiveMinCandles).hasSize(1);
  }

  @Test
  public void multiplePairsThroughPipeline() {
    pipeline.onTrade(trade("BTC/USD", 100.0, 1.0, 0L));
    pipeline.onTrade(trade("ETH/USD", 50.0, 10.0, 0L));

    pipeline.onTrade(trade("BTC/USD", 110.0, 2.0, 60_000L));
    pipeline.onTrade(trade("ETH/USD", 55.0, 5.0, 60_000L));

    ImmutableList<Candle> btcCandles = store.query("BTC/USD", Timeframe.ONE_MINUTE, 0, 60_000L);
    ImmutableList<Candle> ethCandles = store.query("ETH/USD", Timeframe.ONE_MINUTE, 0, 60_000L);
    assertThat(btcCandles).hasSize(1);
    assertThat(ethCandles).hasSize(1);
    assertThat(btcCandles.get(0).getOpen()).isEqualTo(100.0);
    assertThat(ethCandles.get(0).getOpen()).isEqualTo(50.0);
  }

  @Test
  public void latestCandlesReturnedInReverseOrder() {
    // Create 3 candles by sending trades across 4 intervals.
    pipeline.onTrade(trade("BTC/USD", 100.0, 1.0, 0L));
    pipeline.onTrade(trade("BTC/USD", 110.0, 2.0, 60_000L));
    pipeline.onTrade(trade("BTC/USD", 120.0, 3.0, 120_000L));
    pipeline.onTrade(trade("BTC/USD", 130.0, 4.0, 180_000L));

    ImmutableList<Candle> latest = store.latest("BTC/USD", Timeframe.ONE_MINUTE, 2);
    assertThat(latest).hasSize(2);
    // Most recent first.
    assertThat(latest.get(0).getOpen()).isEqualTo(120.0);
    assertThat(latest.get(1).getOpen()).isEqualTo(110.0);
  }

  @Test
  public void simulatedTradeStream() {
    // Simulate a stream of 100 trades over 10 minutes.
    long baseTime = 0L;
    double price = 100.0;
    for (int i = 0; i < 100; i++) {
      long tradeTime = baseTime + (i * 6_000L); // Every 6 seconds.
      price += (i % 2 == 0) ? 0.5 : -0.3;
      pipeline.onTrade(trade("BTC/USD", price, 0.1 + (i * 0.01), tradeTime));
    }
    pipeline.flush();

    // 10 minutes of trades at 6s intervals = 10 one-minute candles.
    ImmutableList<Candle> oneMinCandles = store.query("BTC/USD", Timeframe.ONE_MINUTE, 0, 600_000L);
    assertThat(oneMinCandles).hasSize(10);

    // 2 five-minute candles.
    ImmutableList<Candle> fiveMinCandles =
        store.query("BTC/USD", Timeframe.FIVE_MINUTES, 0, 600_000L);
    assertThat(fiveMinCandles).hasSize(2);

    // Verify all candles have valid OHLCV.
    for (Candle c : oneMinCandles) {
      assertThat(c.getHigh()).isAtLeast(c.getOpen());
      assertThat(c.getHigh()).isAtLeast(c.getClose());
      assertThat(c.getLow()).isAtMost(c.getOpen());
      assertThat(c.getLow()).isAtMost(c.getClose());
      assertThat(c.getVolume()).isGreaterThan(0.0);
    }
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
