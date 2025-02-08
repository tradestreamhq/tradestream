package com.verlumen.tradestream.marketdata;

import com.google.protobuf.Timestamp;
import com.verlumen.tradestream.marketdata.Trade;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.joda.time.Instant;
import java.math.BigDecimal;

/**
 * DefaultTradeGenerator generates synthetic Trade messages for a given key.
 * The generated trade has zero volume and uses a default price.
 */
public class DefaultTradeGenerator extends PTransform<PCollection<KV<String, Void>>, PCollection<KV<String, Trade>>> {

    private final BigDecimal defaultPrice;

    public DefaultTradeGenerator(BigDecimal defaultPrice) {
        this.defaultPrice = defaultPrice;
    }

    @Override
    public PCollection<KV<String, Trade>> expand(PCollection<KV<String, Void>> input) {
        return input.apply("GenerateDefaultTrades", ParDo.of(new DefaultTradeGeneratorFn(defaultPrice)));
    }

    public static class DefaultTradeGeneratorFn extends DoFn<KV<String, Void>, KV<String, Trade>> {
        private final BigDecimal defaultPrice;

        public DefaultTradeGeneratorFn(BigDecimal defaultPrice) {
            this.defaultPrice = defaultPrice;
        }

        @ProcessElement
        public void processElement(@Element KV<String, Void> element, OutputReceiver<KV<String, Trade>> out) {
            String key = element.getKey();
            String[] parts = key.split("/");
            CurrencyPair pair = CurrencyPair.newBuilder()
                    .setBase(parts[0])
                    .setQuote(parts[1])
                    .build();
            Instant now = Instant.now();
            Timestamp ts = Timestamp.newBuilder().setSeconds(now.getMillis() / 1000).build();
            Trade trade = Trade.newBuilder()
                    .setTimestamp(ts)
                    .setExchange("DEFAULT")
                    .setCurrencyPair(pair)
                    .setPrice(defaultPrice)
                    .setVolume(BigDecimal.ZERO)
                    .setTradeId("DEFAULT-" + key + "-" + now.getMillis())
                    .build();
            out.output(KV.of(key, trade));
        }
    }
}
