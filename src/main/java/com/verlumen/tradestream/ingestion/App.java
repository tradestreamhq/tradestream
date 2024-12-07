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
    logger.atInfo().log("Creating App instance with runMode: %s", runMode);
    this.realTimeDataIngestion = realTimeDataIngestion;
    this.runMode = runMode;
  }

  void run() {
    logger.atInfo().log("Starting real-time data ingestion...");
    logger.atInfo().log("Starting application in %s mode", runMode);
    if (runMode == RunMode.DRY) {
      logger.atInfo().log("Dry run mode detected - skipping data ingestion");
      return;
    }
    
    try {
      logger.atInfo().log("Initiating real-time data ingestion...");
      realTimeDataIngestion.start();
      logger.atInfo().log("Real-time data ingestion started successfully");
    } catch (Exception e) {
      logger.atSevere().withCause(e).log("Failed to start real-time data ingestion");
      throw e;
    }
  }

  public static void main(String[] args) throws Exception {
    logger.atInfo().log("TradeStream application starting up with %d arguments", args.length);
    try {
      logger.atInfo().log("Initializing Guice injector with IngestionModule");
      App app = Guice.createInjector(IngestionModule.create(args)).getInstance(App.class);
      logger.atInfo().log("Guice initialization complete, running application");
      app.run();
    } catch (Exception e) {
      logger.atSevere().withCause(e).log("Fatal error during application startup");
      throw e;
    }
  }
}
