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

  private final StrategyEngine strategyEngine;
  private final MarketDataConsumer marketDataConsumer;
  private volatile boolean isRunning = false;

  @Inject
  App(StrategyEngine strategyEngine, MarketDataConsumer marketDataConsumer) {
    this.strategyEngine = strategyEngine;
    this.marketDataConsumer = marketDataConsumer;
  }

  /** Starts all strategy module components */
  public void start() {
    logger.atInfo().log("Starting real-time strategy discovery...");
    try {
      isRunning = true;
      marketDataConsumer.startConsuming(strategyEngine::handleCandle);
      logger.atInfo().log("Strategy Engine service started successfully");
    } catch (Exception e) {
      logger.atSevere().withCause(e).log("Failed to start Strategy Engine service");
      throw new RuntimeException("Service start failed", e);
    }
  }

  /** Gracefully shuts down the strategy engine and stops consuming market data. */
  public void shutdown() {
    logger.atInfo().log("Shutting down Strategy Engine service...");
    try {
      isRunning = false;
      marketDataConsumer.stopConsuming();
      logger.atInfo().log("Strategy Engine service stopped successfully");
    } catch (Exception e) {
      logger.atSevere().withCause(e).log("Error during Strategy Engine service shutdown");
      // Still throw since we're shutting down anyway
      throw new RuntimeException("Service shutdown failed", e);
    }
  }

  public static void main(String[] args) {
    logger.atInfo().log("Initializing Strategy Engine service...");

    // Initialize dependency injection
    App app = Guice.createInjector(StrategiesModule.create()).getInstance(App.class);

    // Add shutdown hook for graceful termination
    Runtime.getRuntime()
        .addShutdownHook(
            new Thread(
                () -> {
                  logger.atInfo().log("Shutdown hook triggered");
                  app.shutdown();
                }));

    // Start the service
    app.start();
  }
}
