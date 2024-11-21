package com.verlumen.tradestream.ingestion;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Inject;

final class App {
  private static final FluentLogger logger = FluentLogger.forEnclosingClass();

  private final MarketDataIngestion marketDataIngestion;
  private final RunMode runMode;

  @Inject
  App(MarketDataIngestion marketDataIngestion, RunMode runMode) {
    this.marketDataIngestion = marketDataIngestion;
  }

  void run() {
    logger.atInfo().log("Starting real-time data ingestion...");
    if (runMode == RunMode.DRY) return;
    marketDataIngestion.start();
  }

  public static void main(String[] args) throws Exception {
    App app = Guice.createInjector(IngestionModule.create(args)).getInstance(App.class);
    app.run();
  }
}
