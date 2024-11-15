package com.verlumen.tradestream.ingestion;

import com.google.auto.value.AutoValue;

@AutoValue
abstract class CandleKey {
    static CandleKey create(String tradeId, long minuteTimestamp) {
        return new AutoValue_CandleKey(tradeId, minuteTimestamp);
    }
    
    abstract String tradeId();
    abstract long minuteTimestamp();
}
