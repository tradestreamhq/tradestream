package com.verlumen.tradestream.marketdata;

import com.google.inject.Inject;

public class MultiTimeframeCandleTransform
  extends PTransform<PCollection<KV<String, Candle>>, PCollection<KV<String, ImmutableList<Candle>>>> {
  @Inject
  MultiTimeframeCandleTransform() {}

  @Override
  public PCollection<KV<String, ImmutableList<Candle>>> expand(PCollection<KV<String, Candle>> input) {
      // Create a PCollectionList to build up our list of transformations
      PCollectionList<KV<String, ImmutableList<Candle>>> allTimeframes = PCollectionList.empty(input.getPipeline());

      // Apply transformation for each timeframe
      for (TimeFrame timeframe : TimeFrame.values()) {
          PCollection<KV<String, ImmutableList<Candle>>> timeframeCandles = 
              input.apply(
                  "Get " + timeframe.getLabel() + " Window", 
                  ParDo.of(new GetLastNElementsDoFn<>(timeframe.getMinutes()))
              );
          allTimeframes = allTimeframes.and(timeframeCandles);
      }

      // Flatten all timeframes into a single PCollection
      return allTimeframes.apply("Flatten All Timeframes", Flatten.pCollections());
  }
}
