package com.verlumen.tradestream.ingestion;

import com.google.inject.Guice;
import com.google.inject.Inject;

final class App {
  private final MarketDataIngestion marketDataIngestion;

  @Inject
  App(MarketDataIngestion marketDataIngestion) {
    this.marketDataIngestion = marketDataIngestion;
  }

  void run() {
    System.out.println("Starting real-time data ingestion...");
    marketDataIngestion.start();
  }

  public static void main(String... args) throws Exception {
    App app = Guice.createInjector(new IngestionModule()).getInstance(App.class);
    app.run();
  }

}
