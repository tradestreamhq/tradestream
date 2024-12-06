package com.verlumen.tradestream.ingestion;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import info.bitrich.xchangestream.core.StreamingExchange;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class WebSocketHealthMonitor {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    private final StreamingExchange exchange;
    private final ScheduledExecutorService scheduler;
    private static final int HEALTH_CHECK_INTERVAL_SECONDS = 30;

    @Inject
    public WebSocketHealthMonitor(StreamingExchange exchange) {
        this.exchange = exchange;
        this.scheduler = Executors.newSingleThreadScheduledExecutor();
    }

    public void start() {
        scheduler.scheduleAtFixedRate(
            this::checkHealth, 
            HEALTH_CHECK_INTERVAL_SECONDS, 
            HEALTH_CHECK_INTERVAL_SECONDS, 
            TimeUnit.SECONDS
        );
        logger.atInfo().log("WebSocket health monitoring started");
    }

    private void checkHealth() {
        boolean isConnected = exchange.isAlive();
        logger.atInfo().log("WebSocket health check - Connected: %b", isConnected);
        
        if (!isConnected) {
            logger.atSevere().log("WebSocket connection appears to be down!");
        }
    }

    public void stop() {
        logger.atInfo().log("Stopping WebSocket health monitor");
        scheduler.shutdown();
        try {
            if (!scheduler.awaitTermination(5, TimeUnit.SECONDS)) {
                scheduler.shutdownNow();
            }
        } catch (InterruptedException e) {
            scheduler.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }
}
