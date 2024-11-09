package com.verlumen.tradestream.ingestion;

import com.google.inject.Guice;
import com.google.inject.Inject;

final class App {
  private final RealTimeDataIngestion realTimeDataIngestion;

  @Inject
  App(RealTimeDataIngestion realTimeDataIngestion) {
    this.realTimeDataIngestion = realTimeDataIngestion;
  }

  void run() {}

  public static void main(String... args) throws Exception {
    App app = Guice.createInjector().getInstance(App.class);
    System.out.println("Starting real-time data ingestion...");
    app.run();
  }

}
