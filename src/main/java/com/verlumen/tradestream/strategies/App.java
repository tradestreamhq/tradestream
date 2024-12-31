package com.verlumen.tradestream.strategies;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Inject;

/**
 * Main entry point for the Strategy Module. Coordinates data flow between components and manages the
 * lifecycle of the strategy system.
 */
final class App {
  private static final FluentLogger logger = FluentLogger.forEnclosingClass();

  @Inject
  App() {}

  /** Starts all strategy module components */
  public void start() {
    logger.atInfo().log("Starting real-time strategy discovery...");
  }

  /** Gracefully shuts down all strategy module components */
  public void shutdown() {}

  public static void main(String[] args) throws Exception {
    logger.atInfo().log("TradeStream application starting up with %d arguments", args.length);
    App app = Guice.createInjector(StrategiesModule.create(args)).getInstance(App.class);

    // Start the service
    app.start();
  }
}
