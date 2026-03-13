package com.verlumen.tradestream.marketdata;

import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;

/**
 * Coordinates multiple {@link CandleAggregator} instances (one per timeframe) and persists
 * completed candles to a {@link CandleStore}.
 */
public class CandleAggregationPipeline {

  private final ImmutableMap<Timeframe, CandleAggregator> aggregators;
  private final CandleStore store;

  /** Creates a pipeline that aggregates trades into all specified timeframes. */
  public CandleAggregationPipeline(CandleStore store, ImmutableList<Timeframe> timeframes) {
    this.store = store;
    ImmutableMap.Builder<Timeframe, CandleAggregator> builder = ImmutableMap.builder();
    for (Timeframe tf : timeframes) {
      CandleAggregator aggregator = new CandleAggregator(tf);
      aggregator.addListener(candle -> store.store(candle, tf));
      builder.put(tf, aggregator);
    }
    this.aggregators = builder.build();
  }

  /** Creates a pipeline with all supported timeframes. */
  public static CandleAggregationPipeline createDefault(CandleStore store) {
    return new CandleAggregationPipeline(store, ImmutableList.copyOf(Timeframe.values()));
  }

  /** Feed a raw trade into all aggregators. */
  public void onTrade(Trade trade) {
    for (CandleAggregator aggregator : aggregators.values()) {
      aggregator.onTrade(trade);
    }
  }

  /** Flush all aggregators. */
  public void flush() {
    for (CandleAggregator aggregator : aggregators.values()) {
      aggregator.flush();
    }
  }

  /** Get the store backing this pipeline. */
  public CandleStore getStore() {
    return store;
  }
}
