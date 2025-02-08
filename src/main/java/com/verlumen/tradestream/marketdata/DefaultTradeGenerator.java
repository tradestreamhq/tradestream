package com.verlumen.tradestream.marketdata;

import com.google.protobuf.Timestamp;
import com.google.protobuf.util.Timestamps;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.joda.time.Instant;

/**
 * DefaultTradeGenerator generates synthetic Trade messages for a given key.
 * The generated trade has zero volume and uses a default price.
 * This transform ensures that even when there are no real trades,
 * a dummy trade is injected to trigger candle creation downstream.
 */
public class DefaultTradeGenerator extends PTransform<PCollection<KV<String, Void>>, PCollection<KV<String, Trade>>> {

    private final double defaultPrice;

    public DefaultTradeGenerator(double defaultPrice) {
        this.defaultPrice = defaultPrice;
    }

    @Override
    public PCollection<KV<String, Trade>> expand(PCollection<KV<String, Void>> input) {
        return input.apply("GenerateDefaultTrades", ParDo.of(new DefaultTradeGeneratorFn(defaultPrice)));
    }

    public static class DefaultTradeGeneratorFn extends DoFn<KV<String, Void>, KV<String, Trade>> {
        private final double defaultPrice;

        public DefaultTradeGeneratorFn(double defaultPrice) {
            this.defaultPrice = defaultPrice;
        }

        @ProcessElement
        public void processElement(@Element KV<String, Void> element, OutputReceiver<KV<String, Trade>> out) {
            String key = element.getKey();  // Expecting a key like "BTC/USD"
            Instant now = Instant.now();
            Timestamp ts = Timestamps.fromMillis(now.getMillis());
            Trade trade = Trade.newBuilder()
                    .setTimestamp(ts)
                    .setExchange("DEFAULT")
                    .setCurrencyPair(key)
                    .setPrice(defaultPrice)
                    .setVolume(0.0)
                    .setTradeId("DEFAULT-" + key + "-" + now.getMillis())
                    .build();
            out.output(KV.of(key, trade));
        }
    }
}
