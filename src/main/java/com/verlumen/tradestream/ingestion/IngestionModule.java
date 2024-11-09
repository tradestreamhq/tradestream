package com.verlumen.tradestream.ingestion;

import com.google.inject.AbstractModule;

final class IngestionModule extends AbstractModule {
  @Override
  protected void configure() {
    bind(MarketDataIngestion.class).to(RealTimeDataIngestion.class);
  }
}
