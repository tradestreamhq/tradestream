package com.verlumen.tradestream.ingestion;

import com.google.common.flogger.backend.system.DefaultPlatform;
import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Inject;

static {
  System.setProperty(
      "flogger.backend_factory",
      "com.google.common.flogger.backend.system.DefaultPlatform$SystemBackendFactory");
}

final class App {
  private static final FluentLogger logger = FluentLogger.forEnclosingClass();

  private final MarketDataIngestion marketDataIngestion;

  @Inject
  App(MarketDataIngestion marketDataIngestion) {
    this.marketDataIngestion = marketDataIngestion;
  }

  void run() {
    logger.atInfo().log("Starting real-time data ingestion...");
    marketDataIngestion.start();
  }

  public static void main(String... args) throws Exception {
    App app = Guice.createInjector(new IngestionModule()).getInstance(App.class);
    app.run();
  }
}
