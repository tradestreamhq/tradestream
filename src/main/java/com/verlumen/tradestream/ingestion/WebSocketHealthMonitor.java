package com.verlumen.tradestream.ingestion;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import info.bitrich.xchangestream.core.StreamingExchange;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Monitors the health of WebSocket connections to cryptocurrency exchanges.
 * Performs periodic health checks and logs connection status.
 * 
 * This monitor:
 * - Runs health checks at configurable intervals
 * - Logs connection status changes
 * - Attempts reconnection when connection is lost
 * - Provides clean shutdown handling
 */
class WebSocketHealthMonitor {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    
    // Run health checks every 30 seconds by default
    private static final int HEALTH_CHECK_INTERVAL_SECONDS = 30;
    
    // Maximum time to wait for graceful shutdown
    private static final int SHUTDOWN_TIMEOUT_SECONDS = 5;

    private final StreamingExchange exchange;
    private final ScheduledExecutorService scheduler;
    private boolean isRunning;

    /**
     * Creates a new WebSocket health monitor.
     *
     * @param exchange The streaming exchange to monitor
     * @param scheduler Scheduler for periodic health checks
     */
    @Inject
    WebSocketHealthMonitor(StreamingExchange exchange, ScheduledExecutorService scheduler) {
        this.exchange = exchange;
        this.scheduler = scheduler;
        this.isRunning = false;
    }

    /**
     * Starts the health monitoring service.
     * Schedules periodic health checks at fixed intervals.
     */
    public void start() {
        if (isRunning) {
            logger.atWarning().log("Health monitor is already running");
            return;
        }

        scheduler.scheduleAtFixedRate(
            this::checkHealth,
            HEALTH_CHECK_INTERVAL_SECONDS,
            HEALTH_CHECK_INTERVAL_SECONDS,
            TimeUnit.SECONDS
        );
        isRunning = true;
        logger.atInfo().log("WebSocket health monitoring started");
    }

    /**
     * Performs a health check of the WebSocket connection.
     * Attempts reconnection if the connection is down.
     */
    private void checkHealth() {
        try {
            boolean isConnected = exchange.isAlive();
            logger.atInfo().log("WebSocket health check - Connected: %b", isConnected);
            
            if (!isConnected) {
                logger.atSevere().log("WebSocket connection appears to be down! Attempting reconnect...");
                attemptReconnect();
            }
        } catch (Exception e) {
            logger.atSevere().withCause(e).log("Error during health check");
        }
    }

    /**
     * Attempts to reconnect to the exchange by:
     * 1. Disconnecting the current session (if any)
     * 2. Establishing a new connection
     * 
     * Will timeout after 5 seconds for each operation.
     */
    private void attemptReconnect() {
        try {
            // First disconnect existing connection
            exchange.disconnect().get(SHUTDOWN_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            
            // Then establish new connection
            exchange.connect().get(SHUTDOWN_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            logger.atInfo().log("Successfully reconnected WebSocket");
        } catch (Exception e) {
            logger.atSevere().withCause(e).log("Failed to reconnect WebSocket");
        }
    }

    /**
     * Stops the health monitoring service.
     * Attempts graceful shutdown of the scheduler.
     */
    public void stop() {
        if (!isRunning) {
            logger.atWarning().log("Health monitor is not running");
            return;
        }

        logger.atInfo().log("Stopping WebSocket health monitor");
        scheduler.shutdown();
        try {
            if (!scheduler.awaitTermination(SHUTDOWN_TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
                scheduler.shutdownNow();
            }
        } catch (InterruptedException e) {
            scheduler.shutdownNow();
            Thread.currentThread().interrupt();
        }
        isRunning = false;
    }

    /**
     * @return true if the health monitor is currently running
     */
    public boolean isRunning() {
        return isRunning;
    }
}
