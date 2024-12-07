package com.verlumen.tradestream.ingestion;

import com.google.common.collect.ImmutableList;
import com.google.common.flogger.FluentLogger;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.inject.Inject;
import com.verlumen.tradestream.marketdata.Trade;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.Consumer;

final class CoinbaseStreamingClient implements ExchangeStreamingClient {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    private static final String WEBSOCKET_URL = "wss://advanced-trade-ws.coinbase.com";
    private static final int PRODUCTS_PER_CONNECTION = 15;
    
    private final Map<WebSocket, List<String>> connectionProducts;
    private final List<WebSocket> connections;
    private final HttpClient httpClient;
    private final Map<WebSocket, CompletableFuture<Void>> pendingMessages;
    private Consumer<Trade> tradeHandler;

    @Inject
    CoinbaseStreamingClient(HttpClient httpClient) {
        this.connectionProducts = new ConcurrentHashMap<>();
        this.connections = new CopyOnWriteArrayList<>();
        this.httpClient = httpClient;
        this.pendingMessages = new ConcurrentHashMap<>();
    }

    @Override
    public void startStreaming(ImmutableList<String> currencyPairs, Consumer<Trade> tradeHandler) {       
        // Convert currency pairs to Coinbase product IDs
        ImmutableList<String> productIds = currencyPairs.stream()
            .map(pair -> pair.replace("/", "-"))
            .collect(ImmutableList.toImmutableList());

        logger.atInfo().log("Starting Coinbase streaming for %d products: %s", 
            productIds.size(), productIds);

        // Split products into groups and create connections
        List<List<String>> productGroups = splitProductsIntoGroups(productIds);
        for (List<String> group : productGroups) {
            connectToWebSocket(group);
        }
    }

    @Override
    public void stopStreaming() {
        logger.atInfo().log("Stopping Coinbase streaming...");
        for (WebSocket ws : connections) {
            try {
                ws.sendClose(WebSocket.NORMAL_CLOSURE, "Shutting down");
                logger.atFine().log("Closed WebSocket connection");
            } catch (Exception e) {
                logger.atWarning().withCause(e).log("Error closing WebSocket connection");
            }
        }
        connections.clear();
        connectionProducts.clear();
    }

    @Override
    public String getExchangeName() {
        return "coinbase";
    }

    private List<List<String>> splitProductsIntoGroups(List<String> productIds) {
        List<List<String>> groups = new ArrayList<>();
        for (int i = 0; i < productIds.size(); i += PRODUCTS_PER_CONNECTION) {
            int end = Math.min(i + PRODUCTS_PER_CONNECTION, productIds.size());
            groups.add(productIds.subList(i, end));
        }
        return groups;
    }

    private void connectToWebSocket(List<String> productIds) {
        try {
            WebSocket.Builder builder = httpClient.newWebSocketBuilder();
            WebSocket webSocket = builder.buildAsync(URI.create(WEBSOCKET_URL), new WebSocketListener())
                .join();
            connections.add(webSocket);
            connectionProducts.put(webSocket, new ArrayList<>(productIds));
            subscribe(webSocket, productIds);
            
            // Subscribe to heartbeats only on the first connection
            if (connections.size() == 1) {
                subscribeToHeartbeat(webSocket);
            }
        } catch (Exception e) {
            logger.atSevere().withCause(e).log("Failed to establish WebSocket connection");
            throw new RuntimeException("WebSocket connection failed", e);
        }
    }

    private void subscribe(WebSocket webSocket, List<String> productIds) {
        JsonObject subscribeMessage = new JsonObject();
        subscribeMessage.addProperty("type", "subscribe");
        subscribeMessage.addProperty("channel", "market_trades");
        
        JsonArray productIdsArray = new JsonArray();
        productIds.forEach(productIdsArray::add);
        subscribeMessage.add("product_ids", productIdsArray);
        
        webSocket.sendText(subscribeMessage.toString(), true);
        logger.atInfo().log("Sent subscription message for %d products: %s", 
            productIds.size(), productIds);
    }

    private void subscribeToHeartbeat(WebSocket webSocket) {
        JsonObject heartbeatMessage = new JsonObject();
        heartbeatMessage.addProperty("type", "subscribe");
        heartbeatMessage.addProperty("channel", "heartbeats");
        
        webSocket.sendText(heartbeatMessage.toString(), true);
        logger.atInfo().log("Subscribed to heartbeat channel");
    }

    private void handleMessage(JsonObject message) {
        if (!message.has("channel")) {
            logger.atWarning().log("Received message without channel field: %s", message);
            return;
        }

        String channel = message.get("channel").getAsString();
        
        if ("heartbeats".equals(channel)) {
            logger.atFine().log("Received heartbeat");
            return;
        }

        if (!"market_trades".equals(channel)) {
            logger.atFine().log("Ignoring message from unknown channel: %s", channel);
            return;
        }

        if (!message.has("events")) {
            logger.atWarning().log("Market trades message missing events field: %s", message);
            return;
        }
    
        JsonElement eventsElement = message.get("events");
        if (!eventsElement.isJsonArray()) {
            logger.atWarning().log("Events field is not an array: %s", message);
            return;
        }

        JsonArray events = eventsElement.getAsJsonArray();
        for (JsonElement event : events) {
            JsonObject eventObj = event.getAsJsonObject();
            if (!eventObj.has("trades")) {
                logger.atWarning().log("Event missing trades array: %s", eventObj);
                continue;
            }
            
            JsonElement tradesElement = eventObj.get("trades");
            if (!tradesElement.isJsonArray()) {
                logger.atWarning().log("Trades field is not an array: %s", eventObj);
                continue;
            }
            
            JsonArray trades = tradesElement.getAsJsonArray();
            trades.forEach(tradeElement -> {
                try {
                    JsonObject tradeJson = tradeElement.getAsJsonObject();
                    
                    long timestamp = Instant.parse(tradeJson.get("time").getAsString()).toEpochMilli();
                    
                    Trade trade = Trade.newBuilder()
                        .setTimestamp(timestamp)
                        .setExchange(getExchangeName())
                        .setCurrencyPair(tradeJson.get("product_id").getAsString().replace("-", "/"))
                        .setPrice(tradeJson.get("price").getAsDouble())
                        .setVolume(tradeJson.get("size").getAsDouble())
                        .setTradeId(tradeJson.get("trade_id").getAsString())
                        .build();
    
                    if (tradeHandler != null) {
                        tradeHandler.accept(trade);
                    } else {
                        logger.atWarning().log("Received trade but no handler is registered");
                    }
                } catch (Exception e) {
                    logger.atWarning().withCause(e).log("Failed to process trade: %s", tradeElement);
                }
            });
        }
    }

    private class WebSocketListener implements WebSocket.Listener {
        private final StringBuilder messageBuffer = new StringBuilder();

        @Override
        public CompletionStage<?> onText(WebSocket webSocket, CharSequence data, boolean last) {
            messageBuffer.append(data);
            
            if (last) {
                String message = messageBuffer.toString();
                messageBuffer.setLength(0); // Clear buffer
                
                try {
                    handleMessage(JsonParser.parseString(message).getAsJsonObject());
                } catch (Exception e) {
                    logger.atWarning().withCause(e).log("Failed to parse message: %s", message);
                }
            }
            
            return CompletableFuture.completedFuture(null);
        }

        @Override
        public CompletionStage<?> onClose(WebSocket webSocket, int statusCode, String reason) {
            logger.atInfo().log("WebSocket closed: %d %s", statusCode, reason);
            connections.remove(webSocket);
            
            // Only attempt reconnection for non-normal closures
            if (statusCode != WebSocket.NORMAL_CLOSURE && !connections.isEmpty()) {
                List<String> productIds = connectionProducts.remove(webSocket);
                if (productIds != null && !productIds.isEmpty()) {
                    logger.atInfo().log("Attempting to reconnect for products: %s", productIds);
                    connectToWebSocket(productIds);
                }
            }
            
            return CompletableFuture.completedFuture(null);
        }

        @Override
        public void onError(WebSocket webSocket, Throwable error) {
            logger.atSevere().withCause(error).log("WebSocket error");
        }
    }
}
