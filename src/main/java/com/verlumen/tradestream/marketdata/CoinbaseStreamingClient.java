package com.verlumen.tradestream.marketdata;

import static com.google.common.collect.Streams.stream;
import static com.google.common.collect.ImmutableList.toImmutableList;
import static com.google.protobuf.util.Timestamps.fromMillis;

import com.google.common.collect.ImmutableList;
import com.google.common.flogger.FluentLogger;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.inject.Inject;
import com.verlumen.tradestream.instruments.CurrencyPair;
import java.io.IOException;
import java.io.Serializable;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.URI;
import java.net.http.WebSocket;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
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
    private transient HttpClient httpClient;
    private final Map<WebSocket, CompletableFuture<Void>> pendingMessages;
    // Map to track the last timestamp for each currency pair
    private final Map<String, Long> lastTimestampByCurrencyPair;
    private transient Consumer<Trade> tradeHandler;
    private transient WebSocketConnector connector;
    private transient MessageHandler messageHandler;

    @Inject
    CoinbaseStreamingClient(HttpClient httpClient) {
        this.connectionProducts = new ConcurrentHashMap<>();
        this.connections = new CopyOnWriteArrayList<>();
        this.httpClient = httpClient;
        this.pendingMessages = new ConcurrentHashMap<>();
        this.lastTimestampByCurrencyPair = new ConcurrentHashMap<>();
        this.connector = new WebSocketConnector(this);
        this.messageHandler = new MessageHandler(this);
    }

    private void writeObject(java.io.ObjectOutputStream out) throws IOException {
        out.defaultWriteObject();
        // Only serialize what's needed - httpClient, tradeHandler, connector, and messageHandler are transient
    }

    private void readObject(java.io.ObjectInputStream in) throws IOException, ClassNotFoundException {
        in.defaultReadObject();
        // Recreate the transient fields during deserialization
        this.httpClient = HttpClient.newBuilder().build();
        this.connector = new WebSocketConnector(this);
        this.messageHandler = new MessageHandler(this);
        // Note: tradeHandler will be set when startStreaming is called
    }

    @Override
    public void startStreaming(ImmutableList<CurrencyPair> currencyPairs, Consumer<Trade> tradeHandler) {
        this.tradeHandler = tradeHandler;

        // Convert currency pairs to Coinbase product IDs
        ImmutableList<String> productIds = convertToProductIds(currencyPairs);
        logger.atInfo().log("Starting Coinbase streaming for %d products: %s", 
            productIds.size(), productIds);

        List<List<String>> productGroups = splitProductsIntoGroups(productIds);
        connectToAllProductGroups(productGroups);
    }
    
    private ImmutableList<String> convertToProductIds(ImmutableList<CurrencyPair> currencyPairs) {
        return currencyPairs.stream()
            .map(CoinbaseStreamingClient::createProductId)
            .collect(toImmutableList());
    }
    
    private void connectToAllProductGroups(List<List<String>> productGroups) {
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
        // Clear timestamp tracking when stopping
        lastTimestampByCurrencyPair.clear();
    }

    @Override
    public String getExchangeName() {
        return "coinbase";
    }

    /**
     * Fetches the list of supported currency pairs from the Coinbase API.
     * 
     * @return an immutable list of supported CurrencyPairs.
     */
    @Override
    public ImmutableList<CurrencyPair> supportedCurrencyPairs() {
        logger.atInfo().log("Fetching supported currency pairs from Coinbase");
        
        String url = "https://api.exchange.coinbase.com/products";
        HttpRequest request = createHttpRequest(url);
        
        try {
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            
            if (response.statusCode() != 200) {
                logger.atWarning().log("Failed to fetch supported products from Coinbase. Status: %d, Response: %s",
                    response.statusCode(), response.body());
                return ImmutableList.of();
            }
            
            return parseResponseToJsonArray(response.body())
                .map(this::extractCurrencyPairsFromProductsArray)
                .map(pairs -> {
                    logger.atInfo().log("Retrieved %d supported currency pairs", pairs.size());
                    return pairs;
                })
                .orElseGet(() -> {
                    logger.atWarning().log("Failed to parse JSON response from Coinbase");
                    return ImmutableList.of();
                });
        } catch (IOException | InterruptedException e) {
            logger.atSevere().withCause(e).log("Error fetching supported products from Coinbase");
            return ImmutableList.of();
        }
    }
    
    private HttpRequest createHttpRequest(String url) {
        return HttpRequest.newBuilder()
            .uri(URI.create(url))
            .header("Accept", "application/json")
            .build();
    }
    
    private Optional<JsonArray> parseResponseToJsonArray(String responseBody) {
        try {
            JsonElement jsonElement = JsonParser.parseString(responseBody);
            if (!jsonElement.isJsonArray()) {
                logger.atWarning().log("Expected a JSON array of products but received: %s", responseBody);
                return Optional.empty();
            }
            return Optional.of(jsonElement.getAsJsonArray());
        } catch (Exception e) {
            logger.atWarning().withCause(e).log("Failed to parse response as JSON array: %s", responseBody);
            return Optional.empty();
        }
    }
    
    private ImmutableList<CurrencyPair> extractCurrencyPairsFromProductsArray(JsonArray productsArray) {
        return stream(productsArray)
            .filter(JsonElement::isJsonObject)
            .map(JsonElement::getAsJsonObject)
            .filter(obj -> obj.has("id"))
            .map(obj -> obj.get("id").getAsString())
            .map(CurrencyPair::fromSymbol)
            .collect(toImmutableList());
    }

    private static String createProductId(CurrencyPair currencyPair) {
        return currencyPair.base().symbol() + "-" + currencyPair.counter().symbol();
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

    private static class MessageHandler implements Serializable {
        private static final FluentLogger logger = FluentLogger.forEnclosingClass();
        private final CoinbaseStreamingClient client;

        MessageHandler(CoinbaseStreamingClient client) {
            this.client = client;
        }

        void handle(JsonObject message) {
            logger.atFiner().log("Received message: %s", message);

            getMessageChannel(message)
                .filter(channel -> !isHeartbeat(channel))
                .filter(this::isMarketTradesChannel)
                .flatMap(channel -> getEventsArray(message))
                .ifPresent(this::processEvents);
        }

        private boolean isHeartbeat(String channel) {
            if ("heartbeats".equals(channel)) {
                logger.atFine().log("Received heartbeat");
                return true;
            }
            return false;
        }

        private boolean isMarketTradesChannel(String channel) {
            if (!"market_trades".equals(channel)) {
                logger.atFine().log("Ignoring message from unknown channel: %s", channel);
                return false;
            }
            return true;
        }

        private Optional<String> getMessageChannel(JsonObject message) {
            if (!message.has("channel")) {
                logger.atWarning().log("Received message without 'channel' field: %s", message);
                return Optional.empty();
            }
            return Optional.of(message.get("channel").getAsString());
        }

        private Optional<JsonArray> getEventsArray(JsonObject message) {
            if (!message.has("events")) {
                logger.atWarning().log("Market trades message missing 'events' field: %s", message);
                return Optional.empty();
            }

            JsonElement eventsElement = message.get("events");
            if (!eventsElement.isJsonArray()) {
                logger.atWarning().log("'events' field is not an array: %s", message);
                return Optional.empty();
            }

            return Optional.of(eventsElement.getAsJsonArray());
        }

        private void processEvents(JsonArray events) {
            stream(events)
                .map(JsonElement::getAsJsonObject)
                .map(this::getTradesArray)
                .flatMap(Optional::stream)
                .forEach(this::processTrades);
        }

        private Optional<JsonArray> getTradesArray(JsonObject eventObj) {
            if (!eventObj.has("trades")) {
                logger.atWarning().log("Event missing 'trades' array: %s", eventObj);
                return Optional.empty();
            }

            JsonElement tradesElement = eventObj.get("trades");
            if (!tradesElement.isJsonArray()) {
                logger.atWarning().log("'trades' field is not an array: %s", eventObj);
                return Optional.empty();
            }

            return Optional.of(tradesElement.getAsJsonArray());
        }

        private void processTrades(JsonArray trades) {
            stream(trades).forEach(this::processTrade);
        }

        private void processTrade(JsonElement tradeElement) {
            try {
                JsonObject tradeJson = tradeElement.getAsJsonObject();
                logger.atFiner().log("Processing trade: %s", tradeJson);

                extractTradeInfo(tradeJson)
                    .filter(info -> isTradeNewerThanLastProcessed(info.currencyPair(), info.timestamp()))
                    .ifPresent(info -> {
                        // Update the last timestamp for this currency pair
                        client.lastTimestampByCurrencyPair.put(info.currencyPair(), info.timestamp());
                        
                        // Build and process the trade
                        buildTrade(tradeJson, info)
                            .ifPresent(trade -> {
                                if (client.tradeHandler != null) {
                                    client.tradeHandler.accept(trade);
                                } else {
                                    logger.atWarning().log("Received trade but no handler is registered");
                                }
                            });
                    });
            } catch (Exception e) {
                logger.atWarning().withCause(e).log("Failed to process trade: %s", tradeElement);
            }
        }

        private Optional<TradeInfo> extractTradeInfo(JsonObject tradeJson) {
            try {
                long timestamp = Instant.parse(tradeJson.get("time").getAsString()).toEpochMilli();
                String currencyPair = getFormattedCurrencyPair(tradeJson);
                return Optional.of(new TradeInfo(currencyPair, timestamp));
            } catch (Exception e) {
                logger.atWarning().withCause(e).log("Failed to extract trade info: %s", tradeJson);
                return Optional.empty();
            }
        }

        private record TradeInfo(String currencyPair, long timestamp) {}

        private String getFormattedCurrencyPair(JsonObject tradeJson) {
            String productId = tradeJson.get("product_id").getAsString();
            return productId.replace("-", "/");
        }

        private boolean isTradeNewerThanLastProcessed(String currencyPairStr, long timestamp) {
            Long lastTimestamp = client.lastTimestampByCurrencyPair.get(currencyPairStr);
            if (lastTimestamp != null && timestamp <= lastTimestamp) {
                logger.atFine().log(
                    "Skipping out-of-order trade for %s: current timestamp %d <= last timestamp %d",
                    currencyPairStr, timestamp, lastTimestamp);
                return false;
            }
            return true;
        }

        private Optional<Trade> buildTrade(JsonObject tradeJson, TradeInfo info) {
            try {
                Trade trade = Trade.newBuilder()
                    .setTimestamp(fromMillis(info.timestamp()))
                    .setExchange(client.getExchangeName())
                    .setCurrencyPair(info.currencyPair())
                    .setPrice(tradeJson.get("price").getAsDouble())
                    .setVolume(tradeJson.get("size").getAsDouble())
                    .setTradeId(tradeJson.get("trade_id").getAsString())
                    .build();
                return Optional.of(trade);
            } catch (Exception e) {
                logger.atWarning().withCause(e).log("Failed to build trade from: %s", tradeJson);
                return Optional.empty();
            }
        }
    }

    private static class WebSocketConnector implements Serializable {
        private static final FluentLogger logger = FluentLogger.forEnclosingClass();
        private final CoinbaseStreamingClient client;

        WebSocketConnector(CoinbaseStreamingClient client) {
            this.client = client;
        }

        void connect(List<String> productIds) {
            logger.atInfo().log("Attempting to connect WebSocket for products: %s", productIds);
            
            // Ensure HttpClient exists
            if (client.httpClient == null) {
                client.httpClient = HttpClient.newBuilder().build();
                logger.atInfo().log("Created new HttpClient instance during connect");
            }
            
            // Build the WebSocket connection
            WebSocket.Builder builder = client.httpClient.newWebSocketBuilder();
            builder.buildAsync(
                URI.create(WEBSOCKET_URL), 
                new WebSocketListener(client, productIds)
            )
            .thenAccept(webSocket -> handleSuccessfulConnection(webSocket, productIds))
            .exceptionally(ex -> handleConnectionFailure(ex, productIds));
        }
        
        private void handleSuccessfulConnection(WebSocket webSocket, List<String> productIds) {
            logger.atInfo().log("Successfully connected to Coinbase WebSocket");
            client.connections.add(webSocket);
            client.connectionProducts.put(webSocket, new ArrayList<>(productIds));
            client.subscribe(webSocket, productIds);
            
            if (client.connections.size() == 1) {
                client.subscribeToHeartbeat(webSocket);
            }
        }
        
        private Void handleConnectionFailure(Throwable ex, List<String> productIds) {
            logger.atSevere().withCause(ex)
                .log("Failed to establish WebSocket connection for products: %s", productIds);
            return null;
        }
    }

    private static class WebSocketListener implements WebSocket.Listener, Serializable {
        private static final FluentLogger logger = FluentLogger.forEnclosingClass();
        private transient StringBuilder messageBuffer;
        private final CoinbaseStreamingClient client;
        private final List<String> productIds;

        WebSocketListener(CoinbaseStreamingClient client, List<String> productIds) {
            this.messageBuffer = new StringBuilder();
            this.client = client;
            this.productIds = productIds;
        }
        
        private void writeObject(java.io.ObjectOutputStream out) throws IOException {
            out.defaultWriteObject();
        }

        private void readObject(java.io.ObjectInputStream in) throws IOException, ClassNotFoundException {
            in.defaultReadObject();
            this.messageBuffer = new StringBuilder();
        }

        @Override
        public CompletionStage<?> onText(WebSocket webSocket, CharSequence data, boolean last) {
            messageBuffer.append(data);
            
            if (last) {
                String message = messageBuffer.toString();
                messageBuffer.setLength(0); // Clear buffer
                processCompleteMessage(message);
            }
            
            // Request next frame
            webSocket.request(1);
            return CompletableFuture.completedFuture(null);
        }
        
        private void processCompleteMessage(String message) {
            logger.atFiner().log("Complete message received: %s", message);
            
            try {
                JsonObject jsonMessage = JsonParser.parseString(message).getAsJsonObject();
                client.messageHandler.handle(jsonMessage);
            } catch (Exception e) {
                logger.atWarning().withCause(e).log("Failed to parse message: %s", message);
            }
        }

        @Override
        public CompletionStage<?> onClose(WebSocket webSocket, int statusCode, String reason) {
            logger.atInfo().log("WebSocket closed: %d %s", statusCode, reason);
            client.connections.remove(webSocket);
    
            if (statusCode != WebSocket.NORMAL_CLOSURE) {
                attemptReconnection(webSocket);
            }
            
            return CompletableFuture.completedFuture(null);
        }
        
        private void attemptReconnection(WebSocket webSocket) {
            List<String> products = client.connectionProducts.remove(webSocket);
            if (products != null && !products.isEmpty()) {
                logger.atInfo().log("Attempting to reconnect for products: %s", products);
                client.connector.connect(products);
            }
        }

        @Override
        public void onError(WebSocket webSocket, Throwable error) {
            logger.atSevere().withCause(error).log("WebSocket error occurred");
        }
    }
}
