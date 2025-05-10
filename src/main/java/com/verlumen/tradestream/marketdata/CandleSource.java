package com.verlumen.tradestream.marketdata;

import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;

public abstract class CandleSource extends PTransform<PBegin,PCollection<KV<String, Candle>>> {}
