package com.verlumen.tradestream.marketdata;

import com.google.protobuf.InvalidProtocolBufferException;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.PCollection;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class ParseTrades extends PTransform<PCollection<byte[]>, PCollection<Trade>> {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();

    @Override
    public PCollection<Trade> expand(PCollection<byte[]> input) {
        return input.apply("ParseTradeBytes", ParDo.of(new DoFn<byte[], Trade>() {
            @ProcessElement
            public void processElement(@Element byte[] element, OutputReceiver<Trade> out) {
                try {
                    // Parse the byte array into a Trade instance.
                    Trade trade = Trade.parseFrom(element);
                    out.output(trade);
                } catch (InvalidProtocolBufferException e) {
                    // Log the error. You might also choose to send these bytes to a dead-letter PCollection.
                    logger.atError().log("Failed to parse Trade message from bytes", e);
                }
            }
        }));
    }
}
