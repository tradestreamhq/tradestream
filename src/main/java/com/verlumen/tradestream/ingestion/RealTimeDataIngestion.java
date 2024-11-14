package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;

final class RealTimeDataIngestion implements MarketDataIngestion {
    @Inject
    RealTimeDataIngestion() {}

    @Override
    public void start() {}

    @Override
    public void shutdown() {}
}
