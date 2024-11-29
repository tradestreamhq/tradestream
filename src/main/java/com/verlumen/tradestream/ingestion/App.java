package com.verlumen.tradestream.ingestion;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Inject;

final class App {
  private static final FluentLogger logger = FluentLogger.forEnclosingClass();

  private final RealTimeDataIngestion realTimeDataIngestion;
  private final RunMode runMode;

  @Inject
  App(RealTimeDataIngestion realTimeDataIngestion, RunMode runMode) {
    this.realTimeDataIngestion = realTimeDataIngestion;
    this.runMode = runMode;
  }

  void run() {
    logger.atInfo().log("Starting real-time data ingestion...");
    if (runMode == RunMode.DRY) return;
    realTimeDataIngestion.start();
  }

  public static void main(String[] args) throws Exception {
    App app = Guice.createInjector(IngestionModule.create(args)).getInstance(App.class);
    app.run();
  }
}
