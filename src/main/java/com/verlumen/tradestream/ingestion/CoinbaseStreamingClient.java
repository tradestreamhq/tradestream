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
    private final WebSocketConnector connector;
    private final MessageHandler messageHandler;

    @Inject
    CoinbaseStreamingClient(HttpClient httpClient) {
        this.connectionProducts = new ConcurrentHashMap<>();
        this.connections = new CopyOnWriteArrayList<>();
        this.httpClient = httpClient;
        this.pendingMessages = new ConcurrentHashMap<>();
        this.connector = new WebSocketConnector();
        this.messageHandler = new MessageHandler(this); // Pass reference to parent
    }

    @Override
    public void startStreaming(ImmutableList<String> currencyPairs, Consumer<Trade> tradeHandler) {
        this.tradeHandler = tradeHandler;

        // Convert currency pairs to Coinbase product IDs
        ImmutableList<String> productIds = currencyPairs.stream()
            .map(pair -> pair.replace("/", "-"))
            .collect(ImmutableList.toImmutableList());

        logger.atInfo().log("Starting Coinbase streaming for %d products: %s", 
            productIds.size(), productIds);

        List<List<String>> productGroups = splitProductsIntoGroups(productIds);
        for (List<String> group : productGroups) {
            connector.connect(group);
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

    private void subscribe(WebSocket webSocket, List<String> productIds) {
        logger.atInfo().log("Subscribing to market_trades for products: %s", productIds);
        JsonObject subscribeMessage = new JsonObject();
        subscribeMessage.addProperty("type", "subscribe");
        subscribeMessage.addProperty("channel", "market_trades");
    
        JsonArray productIdsArray = new JsonArray();
        productIds.forEach(productIdsArray::add);
        subscribeMessage.add("product_ids", productIdsArray);
    
        String messageStr = subscribeMessage.toString();
        logger.atFine().log("Sending subscription message: %s", messageStr);
        webSocket.sendText(messageStr, true);
    }

    private void subscribeToHeartbeat(WebSocket webSocket) {
        logger.atInfo().log("Subscribing to heartbeats");
        JsonObject heartbeatMessage = new JsonObject();
        heartbeatMessage.addProperty("type", "subscribe");
        heartbeatMessage.addProperty("channel", "heartbeats");
    
        String messageStr = heartbeatMessage.toString();
        logger.atFine().log("Sending heartbeat subscription message: %s", messageStr);
        webSocket.sendText(messageStr, true);
    }

    /**
     * Static inner class responsible for handling and parsing incoming JSON messages.
     * This class now requires a reference to the outer class instance to access instance-specific fields.
     */
    private static class MessageHandler {
        private final CoinbaseStreamingClient parent;

        MessageHandler(CoinbaseStreamingClient parent) {
            this.parent = parent;
        }

        void handle(JsonObject message) {
            logger.atFiner().log("Received message: %s", message);

            if (!message.has("channel")) {
                logger.atWarning().log("Received message without 'channel' field: %s", message);
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
                logger.atWarning().log("Market trades message missing 'events' field: %s", message);
                return;
            }

            JsonElement eventsElement = message.get("events");
            if (!eventsElement.isJsonArray()) {
                logger.atWarning().log("'events' field is not an array: %s", message);
                return;
            }

            JsonArray events = eventsElement.getAsJsonArray();
            for (JsonElement event : events) {
                JsonObject eventObj = event.getAsJsonObject();
                if (!eventObj.has("trades")) {
                    logger.atWarning().log("Event missing 'trades' array: %s", eventObj);
                    continue;
                }

                JsonElement tradesElement = eventObj.get("trades");
                if (!tradesElement.isJsonArray()) {
                    logger.atWarning().log("'trades' field is not an array: %s", eventObj);
                    continue;
                }

                JsonArray trades = tradesElement.getAsJsonArray();
                trades.forEach(tradeElement -> {
                    try {
                        JsonObject tradeJson = tradeElement.getAsJsonObject();
                        logger.atFiner().log("Processing trade: %s", tradeJson);

                        long timestamp = Instant.parse(tradeJson.get("time").getAsString()).toEpochMilli();

                        Trade trade = Trade.newBuilder()
                            .setTimestamp(timestamp)
                            .setExchange(parent.getExchangeName())
                            .setCurrencyPair(tradeJson.get("product_id").getAsString().replace("-", "/"))
                            .setPrice(tradeJson.get("price").getAsDouble())
                            .setVolume(tradeJson.get("size").getAsDouble())
                            .setTradeId(tradeJson.get("trade_id").getAsString())
                            .build();

                        if (parent.tradeHandler != null) {
                            parent.tradeHandler.accept(trade);
                        } else {
                            logger.atWarning().log("Received trade but no handler is registered");
                        }
                    } catch (Exception e) {
                        logger.atWarning().withCause(e).log("Failed to process trade: %s", tradeElement);
                    }
                });
            }
        }
    }

    private class WebSocketConnector {
        void connect(List<String> productIds) {
            logger.atInfo().log("Attempting to connect WebSocket for products: %s", productIds);
            WebSocket.Builder builder = httpClient.newWebSocketBuilder();
        
            CompletableFuture<WebSocket> futureWs = builder.buildAsync(URI.create(WEBSOCKET_URL), new WebSocketListener());
        
            futureWs
                .thenAccept(webSocket -> {
                    logger.atInfo().log("Successfully connected to Coinbase WebSocket");
                    connections.add(webSocket);
                    connectionProducts.put(webSocket, new ArrayList<>(productIds));
                    subscribe(webSocket, productIds);
                    
                    if (connections.size() == 1) {
                        subscribeToHeartbeat(webSocket);
                    }
                })
                .exceptionally(ex -> {
                    logger.atSevere().withCause(ex)
                        .log("Failed to establish WebSocket connection for products: %s", productIds);
                    return null;
                });
        }

        private void subscribe(WebSocket webSocket, List<String> productIds) {
            logger.atInfo().log("Subscribing to market_trades for products: %s", productIds);
            JsonObject subscribeMessage = new JsonObject();
            subscribeMessage.addProperty("type", "subscribe");
            subscribeMessage.addProperty("channel", "market_trades");
        
            JsonArray productIdsArray = new JsonArray();
            productIds.forEach(productIdsArray::add);
            subscribeMessage.add("product_ids", productIdsArray);
        
            String messageStr = subscribeMessage.toString();
            logger.atFine().log("Sending subscription message: %s", messageStr);
            webSocket.sendText(messageStr, true);
        }

        private void subscribeToHeartbeat(WebSocket webSocket) {
            logger.atInfo().log("Subscribing to heartbeats");
            JsonObject heartbeatMessage = new JsonObject();
            heartbeatMessage.addProperty("type", "subscribe");
            heartbeatMessage.addProperty("channel", "heartbeats");
        
            String messageStr = heartbeatMessage.toString();
            logger.atFine().log("Sending heartbeat subscription message: %s", messageStr);
            webSocket.sendText(messageStr, true);
        }
    }

    private class WebSocketListener implements WebSocket.Listener {
        private final StringBuilder messageBuffer;

        WebSocketListener() {
            this.messageBuffer = new StringBuilder();
        }

        @Override
        public CompletionStage<?> onText(WebSocket webSocket, CharSequence data, boolean last) {
            messageBuffer.append(data);

            if (last) {
                String message = messageBuffer.toString();
                messageBuffer.setLength(0); // Clear buffer
                logger.atFiner().log("Complete message received: %s", message);
                try {
                    JsonObject jsonMessage = JsonParser.parseString(message).getAsJsonObject();
                    messageHandler.handle(jsonMessage);
                } catch (Exception e) {
                    logger.atWarning().withCause(e).log("Failed to parse message: %s", message);
                }
            }

            // Request next frame
            webSocket.request(1);
            return CompletableFuture.completedFuture(null);
        }

        @Override
        public CompletionStage<?> onClose(WebSocket webSocket, int statusCode, String reason) {
            logger.atInfo().log("WebSocket closed: %d %s", statusCode, reason);
            connections.remove(webSocket);
    
            if (statusCode != WebSocket.NORMAL_CLOSURE) {
                List<String> productIds = connectionProducts.remove(webSocket);
                if (productIds != null && !productIds.isEmpty()) {
                    logger.atInfo().log("Attempting to reconnect for products: %s", productIds);
                    connector.connect(productIds);
                }
            }

            return CompletableFuture.completedFuture(null);
        }

        @Override
        public void onError(WebSocket webSocket, Throwable error) {
            logger.atSevere().withCause(error).log("WebSocket error occurred");
        }
    }
}
