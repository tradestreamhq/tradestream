package com.verlumen.tradestream.strategies;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.Module;
import com.verlumen.tradestream.strategies.modules.StrategyModule;

/**
 * Main entry point for the Strategy Engine service. Coordinates initialization and
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

    /**
     * Starts the strategy engine and begins consuming market data.
     */
    public void start() {
        logger.atInfo().log("Starting Strategy Engine service...");
        try {
            isRunning = true;
            marketDataConsumer.startConsuming(strategyEngine::handleCandle);
            logger.atInfo().log("Strategy Engine service started successfully");
        } catch (Exception e) {
            logger.atSevere().withCause(e).log("Failed to start Strategy Engine service");
            throw new RuntimeException("Service start failed", e);
        }
    }

    /**
     * Gracefully shuts down the strategy engine and stops consuming market data.
     */
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
        
        // Create required Guice modules
        Module strategyModule = new StrategyModule();
        
        // Initialize dependency injection
        App app = Guice.createInjector(strategyModule)
            .getInstance(App.class);

        // Add shutdown hook for graceful termination
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            logger.atInfo().log("Shutdown hook triggered");
            app.shutdown();
        }));

        // Start the service
        app.start();
    }
}
