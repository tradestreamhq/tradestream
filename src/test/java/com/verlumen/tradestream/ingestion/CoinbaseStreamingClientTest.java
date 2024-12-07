package com.verlumen.tradestream.ingestion;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

import com.google.common.collect.ImmutableList;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.inject.AbstractModule;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.marketdata.Trade;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.function.Consumer;

@RunWith(JUnit4.class)
public class CoinbaseStreamingClientTest {
    @Rule public MockitoRule mockito = MockitoJUnit.rule();

    private static final String WEBSOCKET_URL = "wss://advanced-trade-ws.coinbase.com";
    private static final ImmutableList<String> TEST_PAIRS = 
        ImmutableList.of("BTC/USD", "ETH/USD");

    @Mock @Bind private Consumer<Trade> mockTradeHandler;
    @Mock @Bind private HttpClient mockHttpClient;
    @Mock private WebSocket mockWebSocket;
    @Mock private WebSocket.Builder mockWebSocketBuilder;

    @Inject private CoinbaseStreamingClient client;
    private ArgumentCaptor<WebSocket.Listener> listenerCaptor;
    private CompletableFuture<WebSocket> webSocketFuture;

    @Before
    public void setUp() {
        listenerCaptor = ArgumentCaptor.forClass(WebSocket.Listener.class);

        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);

        when(mockHttpClient.newWebSocketBuilder()).thenReturn(mockWebSocketBuilder);
        when(mockWebSocketBuilder.buildAsync(any(URI.class), any(WebSocket.Listener.class)))
            .thenReturn(CompletableFuture.completedFuture(mockWebSocket));
        when(mockWebSocket.sendText(anyString(), anyBoolean()))
            .thenReturn(CompletableFuture.completedFuture(null));
    }

    @Test
    public void startStreaming_establishesWebSocketConnection() {
        // Act
        client.startStreaming(TEST_PAIRS, mockTradeHandler);

        // Assert
        verify(mockWebSocketBuilder).buildAsync(
            eq(URI.create(WEBSOCKET_URL)), 
            any(WebSocket.Listener.class)
        );
    }

    @Test
    public void startStreaming_sendsSubscription() {
        // Arrange
        ArgumentCaptor<String> messageCaptor = ArgumentCaptor.forClass(String.class);

        // Act
        client.startStreaming(TEST_PAIRS, mockTradeHandler);

        // Assert
        verify(mockWebSocket).sendText(messageCaptor.capture(), eq(true));

        JsonObject message = JsonParser.parseString(messageCaptor.getValue()).getAsJsonObject();
        assertThat(message.get("type").getAsString()).isEqualTo("subscribe");
        assertThat(message.get("channel").getAsString()).isEqualTo("market_trades");
        assertThat(message.get("product_ids").isJsonArray()).isTrue();

        JsonArray productIds = message.get("product_ids").getAsJsonArray();
        assertThat(productIds.size()).isEqualTo(2);
        assertThat(productIds.get(0).getAsString()).isEqualTo("BTC-USD");
        assertThat(productIds.get(1).getAsString()).isEqualTo("ETH-USD");
    }

    @Test
    public void startStreaming_subscribesToHeartbeat() {
        // Arrange
        ArgumentCaptor<String> messageCaptor = ArgumentCaptor.forClass(String.class);

        // Act
        client.startStreaming(TEST_PAIRS, mockTradeHandler);

        // Assert
        verify(mockWebSocket, atLeastOnce()).sendText(messageCaptor.capture(), eq(true));
        
        boolean foundHeartbeat = messageCaptor.getAllValues().stream()
            .map(JsonParser::parseString)
            .map(JsonElement::getAsJsonObject)
            .anyMatch(json -> 
                "subscribe".equals(json.get("type").getAsString()) &&
                "heartbeats".equals(json.get("channel").getAsString())
            );
            
        assertThat(foundHeartbeat).isTrue();
    }

    @Test
    public void stopStreaming_closesAllConnections() {
        // Arrange
        client.startStreaming(TEST_PAIRS, mockTradeHandler);

        // Act
        client.stopStreaming();

        // Assert
        verify(mockWebSocket).sendClose(eq(WebSocket.NORMAL_CLOSURE), anyString());
    }

    @Test
    public void onText_handlesTrade() {
        // Arrange
        String tradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
                "type": "match",
                "trades": [{
                  "trade_id": "12345",
                  "product_id": "BTC-USD",
                  "price": "50775",
                  "size": "0.00516",
                  "time": "2024-12-07T09:48:31.810058685Z" 
                }]
              }]
            }
            """;
            
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        
        // Capture WebSocket.Listener
        verify(mockWebSocketBuilder).buildAsync(any(), listenerCaptor.capture());
        WebSocket.Listener listener = listenerCaptor.getValue();
    
        // Act
        listener.onText(mockWebSocket, tradeMessage, true);
    
        // Assert
        ArgumentCaptor<Trade> tradeCaptor = ArgumentCaptor.forClass(Trade.class);
        verify(mockTradeHandler).accept(tradeCaptor.capture());
        
        Trade trade = tradeCaptor.getValue();
        assertThat(trade.getTimestamp()).isEqualTo(
            Instant.parse("2024-12-07T09:48:31.810058685Z").toEpochMilli());
        assertThat(trade.getCurrencyPair()).isEqualTo("BTC/USD");
        assertThat(trade.getPrice()).isEqualTo(50775.00);
        assertThat(trade.getVolume()).isEqualTo(0.00516);
        assertThat(trade.getTradeId()).isEqualTo("12345");
        assertThat(trade.getExchange()).isEqualTo("coinbase");
    }

    @Test
    public void onText_handlesHeartbeat() {
        // Arrange
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        
        verify(mockWebSocketBuilder).buildAsync(any(), listenerCaptor.capture());
        WebSocket.Listener listener = listenerCaptor.getValue();

        String heartbeatMessage = """
            {
                "channel": "heartbeats",
                "timestamp": 1234567890
            }
            """;

        // Act
        listener.onText(mockWebSocket, heartbeatMessage, true);

        // Assert
        verifyNoInteractions(mockTradeHandler);
    }

    @Test
    public void onClose_attemptsReconnection() {
        // Arrange
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        
        verify(mockWebSocketBuilder).buildAsync(any(), listenerCaptor.capture());
        WebSocket.Listener listener = listenerCaptor.getValue();

        // Act
        listener.onClose(mockWebSocket, WebSocket.NORMAL_CLOSURE, "Test close");

        // Assert
        // Verify initial connection + reconnection attempt
        verify(mockWebSocketBuilder, times(2))
            .buildAsync(any(URI.class), any(WebSocket.Listener.class));
    }

    @Test
    public void handleMessage_ignoresInvalidMessages() {
        // Arrange
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        
        verify(mockWebSocketBuilder).buildAsync(any(), listenerCaptor.capture());
        WebSocket.Listener listener = listenerCaptor.getValue();

        String invalidMessage = """
            {
                "channel": "market_trades",
                "events": {
                    "not_trades": []
                }
            }
            """;

        // Act
        listener.onText(mockWebSocket, invalidMessage, true);

        // Assert
        verifyNoInteractions(mockTradeHandler);
    }

    @Test
    public void handleMessage_handlesPartialMessages() {
        // Arrange
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        
        verify(mockWebSocketBuilder).buildAsync(any(), listenerCaptor.capture());
        WebSocket.Listener listener = listenerCaptor.getValue();

        String messageStart = """
            {
                "channel": "market_trades",
                "events": {
                    "trades": [{
                        "timestamp": 1234567890,
            """;
        
        String messageEnd = """
                        "product_id": "BTC-USD",
                        "price": "50000.00",
                        "size": "1.0",
                        "trade_id": "12345"
                    }]
                }
            }
            """;

        // Act
        listener.onText(mockWebSocket, messageStart, false);
        listener.onText(mockWebSocket, messageEnd, true);

        // Assert
        verify(mockTradeHandler).accept(any(Trade.class));
    }

    @Test
    public void splitProductsIntoGroups_respectsMaxLimit() {
        // Arrange
        ImmutableList<String> manyPairs = ImmutableList.of(
            "BTC/USD", "ETH/USD", "LTC/USD", "XRP/USD", "ADA/USD",
            "DOT/USD", "LINK/USD", "BCH/USD", "XLM/USD", "UNI/USD",
            "DOGE/USD", "SOL/USD", "MATIC/USD", "ATOM/USD", "AAVE/USD",
            "COMP/USD", "SNX/USD", "YFI/USD", "MKR/USD", "SUSHI/USD"
        );

        // Act
        client.startStreaming(manyPairs, mockTradeHandler);

        // Assert
        // Verify that multiple WebSocket connections were created
        verify(mockWebSocketBuilder, atLeast(2))
            .buildAsync(any(URI.class), any(WebSocket.Listener.class));
    }

    private void captureWebSocketListener() {
        verify(mockWebSocketBuilder).buildAsync(any(), listenerCaptor.capture());
    }

    // Helper method to simulate WebSocket message
    private void simulateWebSocketMessage(String message) {
        WebSocket.Listener listener = listenerCaptor.getValue();
        listener.onText(mockWebSocket, message, true);
    }
}
