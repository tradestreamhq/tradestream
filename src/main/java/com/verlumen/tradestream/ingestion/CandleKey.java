package com.verlumen.tradestream.ingestion;

import java.util.Objects;

final class CandleKey {

    private final String tradeId;
    private final long minuteTimestamp;

    public CandleKey(String tradeId, long minuteTimestamp) {
        this.tradeId = tradeId;
        this.minuteTimestamp = minuteTimestamp;
    }

    public String getTradeId() {
        return tradeId;
    }

    public long getMinuteTimestamp() {
        return minuteTimestamp;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;

        CandleKey candleKey = (CandleKey) o;
        return minuteTimestamp == candleKey.minuteTimestamp &&
                Objects.equals(tradeId, candleKey.tradeId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(tradeId, minuteTimestamp);
    }
}
