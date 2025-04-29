package com.verlumen.tradestream.marketdata;

import static com.google.common.collect.ImmutableList.toImmutableList;
import static com.google.common.truth.Truth.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

import com.google.common.collect.ImmutableList;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.instruments.CurrencyPair;
import com.verlumen.tradestream.marketdata.Trade;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.function.Consumer;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class CoinbaseStreamingClientTest {
    @Rule public MockitoRule mockito = MockitoJUnit.rule();

    private static final String WEBSOCKET_URL = "wss://advanced-trade-ws.coinbase.com";
    private static final ImmutableList<CurrencyPair> TEST_PAIRS = 
        Stream.of("BTC/USD", "ETH/USD")
          .map(CurrencyPair::fromSymbol)
          .collect(toImmutableList());

    @Mock @Bind private Consumer<Trade> mockTradeHandler;
    @Mock @Bind private HttpClient mockHttpClient;
    @Mock private WebSocket mockWebSocket;
    @Mock private WebSocket.Builder mockWebSocketBuilder;

    @Inject private CoinbaseStreamingClient client;
    private ArgumentCaptor<WebSocket.Listener> listenerCaptor;

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
    public void startStreaming_sendsSubscriptions() {
        // Arrange
        ArgumentCaptor<String> messageCaptor = ArgumentCaptor.forClass(String.class);

        // Act
        client.startStreaming(TEST_PAIRS, mockTradeHandler);

        // Assert
        verify(mockWebSocket, times(2)).sendText(messageCaptor.capture(), eq(true));

        // Verify market trades subscription
        JsonObject tradesSub = JsonParser.parseString(messageCaptor.getAllValues().get(0))
            .getAsJsonObject();
        assertThat(tradesSub.get("type").getAsString()).isEqualTo("subscribe");
        assertThat(tradesSub.get("channel").getAsString()).isEqualTo("market_trades");
        assertThat(tradesSub.get("product_ids").getAsJsonArray().size()).isEqualTo(2);

        // Verify heartbeat subscription
        JsonObject heartbeatSub = JsonParser.parseString(messageCaptor.getAllValues().get(1))
            .getAsJsonObject();
        assertThat(heartbeatSub.get("type").getAsString()).isEqualTo("subscribe");
        assertThat(heartbeatSub.get("channel").getAsString()).isEqualTo("heartbeats");
    }

    @Test
    public void onText_handlesTrade() {
        // Arrange
        String tradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
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
        captureWebSocketListener();
        
        // Act
        simulateWebSocketMessage(tradeMessage);
    
        // Assert
        ArgumentCaptor<Trade> tradeCaptor = ArgumentCaptor.forClass(Trade.class);
        verify(mockTradeHandler).accept(tradeCaptor.capture());
        
        Trade trade = tradeCaptor.getValue();
        assertThat(trade.getCurrencyPair()).isEqualTo("BTC/USD");
        assertThat(trade.getPrice()).isEqualTo(50775.00);
        assertThat(trade.getVolume()).isEqualTo(0.00516);
        assertThat(trade.getTradeId()).isEqualTo("12345");
        assertThat(trade.getExchange()).isEqualTo("coinbase");
    }

    @Test
    public void onClose_attemptsReconnection() {
        // Arrange
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        captureWebSocketListener();
        WebSocket.Listener listener = listenerCaptor.getValue();

        // Reset the mock to verify new connection attempts
        reset(mockWebSocketBuilder);
        when(mockWebSocketBuilder.buildAsync(any(URI.class), any(WebSocket.Listener.class)))
            .thenReturn(CompletableFuture.completedFuture(mockWebSocket));

        // Act
        listener.onClose(mockWebSocket, 1006, "Abnormal closure").toCompletableFuture().join();

        // Assert - verify reconnection attempt
        verify(mockWebSocketBuilder, timeout(1000))
            .buildAsync(eq(URI.create(WEBSOCKET_URL)), any(WebSocket.Listener.class));
    }

    @Test
    public void handleMessage_ignoresInvalidMessages() {
        // Arrange
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        captureWebSocketListener();

        String invalidMessage = """
            {
                "channel": "market_trades",
                "events": [{
                    "not_trades": []
                }]
            }
            """;

        // Act
        simulateWebSocketMessage(invalidMessage);

        // Assert
        verifyNoInteractions(mockTradeHandler);
    }

    @Test
    public void handleMessage_handlesPartialMessages() {
        // Arrange
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        captureWebSocketListener();
        WebSocket.Listener listener = listenerCaptor.getValue();

        String messageStart = """
            {
              "channel": "market_trades",
              "events": [{
                "trades": [{
                  "trade_id": "12345",
        """;

        String messageEnd = """
                  "product_id": "BTC-USD",
                  "price": "50775",
                  "size": "0.00516",
                  "time": "2024-12-07T09:48:31.810058685Z"
                }]
              }]
            }
        """;

        // Act
        listener.onText(mockWebSocket, messageStart, false).toCompletableFuture().join();
        listener.onText(mockWebSocket, messageEnd, true).toCompletableFuture().join();

        // Assert
        ArgumentCaptor<Trade> tradeCaptor = ArgumentCaptor.forClass(Trade.class);
        verify(mockTradeHandler, timeout(1000)).accept(tradeCaptor.capture());
        
        Trade trade = tradeCaptor.getValue();
        assertThat(trade.getCurrencyPair()).isEqualTo("BTC/USD");
        assertThat(trade.getPrice()).isEqualTo(50775.00);
        assertThat(trade.getVolume()).isEqualTo(0.00516);
        assertThat(trade.getTradeId()).isEqualTo("12345");
    }

    @Test
    public void handleMessage_skipsOutOfOrderTrades() {
        // Arrange
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        captureWebSocketListener();

        // First trade with timestamp t1
        String firstTradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
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

        // Second trade with EARLIER timestamp t0 (should be skipped)
        String outOfOrderTradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
                "trades": [{
                  "trade_id": "12346",
                  "product_id": "BTC-USD",
                  "price": "50780",
                  "size": "0.00620",
                  "time": "2024-12-07T09:48:30.810058685Z" 
                }]
              }]
            }
            """;

        // Third trade with later timestamp t2 (should be processed)
        String laterTradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
                "trades": [{
                  "trade_id": "12347",
                  "product_id": "BTC-USD",
                  "price": "50790",
                  "size": "0.00720",
                  "time": "2024-12-07T09:48:32.810058685Z" 
                }]
              }]
            }
            """;

        // Act
        simulateWebSocketMessage(firstTradeMessage);   // t1 - processed
        simulateWebSocketMessage(outOfOrderTradeMessage); // t0 - should be skipped
        simulateWebSocketMessage(laterTradeMessage);   // t2 - processed

        // Assert
        ArgumentCaptor<Trade> tradeCaptor = ArgumentCaptor.forClass(Trade.class);
        verify(mockTradeHandler, times(2)).accept(tradeCaptor.capture());
        
        // Verify we only received trades with IDs 12345 and 12347 (not the out-of-order 12346)
        List<String> capturedTradeIds = tradeCaptor.getAllValues().stream()
            .map(Trade::getTradeId)
            .collect(Collectors.toList());
        
        assertThat(capturedTradeIds).containsExactly("12345", "12347");
        assertThat(capturedTradeIds).doesNotContain("12346");
    }

    @Test
    public void handleMessage_processesDifferentCurrencyPairsIndependently() {
        // Arrange
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        captureWebSocketListener();

        // BTC/USD trade at t1
        String btcTradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
                "trades": [{
                  "trade_id": "btc-12345",
                  "product_id": "BTC-USD",
                  "price": "50775",
                  "size": "0.00516",
                  "time": "2024-12-07T09:48:31.810058685Z" 
                }]
              }]
            }
            """;

        // ETH/USD trade at t0 (earlier, but different currency pair)
        String ethTradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
                "trades": [{
                  "trade_id": "eth-12345",
                  "product_id": "ETH-USD",
                  "price": "2100",
                  "size": "0.15",
                  "time": "2024-12-07T09:48:30.810058685Z" 
                }]
              }]
            }
            """;

        // Out-of-order BTC/USD trade at t0 (should be skipped)
        String outOfOrderBtcTradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
                "trades": [{
                  "trade_id": "btc-12346",
                  "product_id": "BTC-USD",
                  "price": "50780",
                  "size": "0.00620",
                  "time": "2024-12-07T09:48:30.810058685Z" 
                }]
              }]
            }
            """;

        // Out-of-order ETH/USD trade at t_minus1 (should be skipped)
        String outOfOrderEthTradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
                "trades": [{
                  "trade_id": "eth-12346",
                  "product_id": "ETH-USD",
                  "price": "2095",
                  "size": "0.10",
                  "time": "2024-12-07T09:48:29.810058685Z" 
                }]
              }]
            }
            """;

        // Act - Send messages in mixed order
        simulateWebSocketMessage(btcTradeMessage);   // BTC t1 - should be processed
        simulateWebSocketMessage(ethTradeMessage);   // ETH t0 - should be processed (different pair)
        simulateWebSocketMessage(outOfOrderBtcTradeMessage); // BTC t0 - should be skipped (out of order)
        simulateWebSocketMessage(outOfOrderEthTradeMessage); // ETH t_minus1 - should be skipped (out of order)

        // Assert
        ArgumentCaptor<Trade> tradeCaptor = ArgumentCaptor.forClass(Trade.class);
        verify(mockTradeHandler, times(2)).accept(tradeCaptor.capture());
        
        // Verify we received exactly one trade for each currency pair with the expected IDs
        List<Trade> capturedTrades = tradeCaptor.getAllValues();
        
        // Sort by currency pair for assertion
        Map<String, List<Trade>> tradesByCurrencyPair = capturedTrades.stream()
            .collect(Collectors.groupingBy(Trade::getCurrencyPair));
        
        assertThat(tradesByCurrencyPair).hasSize(2);
        assertThat(tradesByCurrencyPair.get("BTC/USD")).hasSize(1);
        assertThat(tradesByCurrencyPair.get("ETH/USD")).hasSize(1);
        
        // Verify trade IDs
        assertThat(tradesByCurrencyPair.get("BTC/USD").get(0).getTradeId()).isEqualTo("btc-12345");
        assertThat(tradesByCurrencyPair.get("ETH/USD").get(0).getTradeId()).isEqualTo("eth-12345");
    }

    @Test
    public void handleMessage_acceptsSameCurrencyPairTradesWithIdenticalTimestamps() {
        // Arrange
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        captureWebSocketListener();

        // First trade for BTC/USD
        String firstTradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
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

        // Second trade for BTC/USD with exact same timestamp
        // This would typically happen with high-frequency trading or batched updates
        String sameTimestampTradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
                "trades": [{
                  "trade_id": "12346",
                  "product_id": "BTC-USD",
                  "price": "50776",
                  "size": "0.00620",
                  "time": "2024-12-07T09:48:31.810058685Z" 
                }]
              }]
            }
            """;

        // Third trade with later timestamp (should be processed)
        String laterTradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
                "trades": [{
                  "trade_id": "12347",
                  "product_id": "BTC-USD",
                  "price": "50790",
                  "size": "0.00720",
                  "time": "2024-12-07T09:48:32.810058685Z" 
                }]
              }]
            }
            """;

        // Act
        simulateWebSocketMessage(firstTradeMessage);       // First trade - processed
        simulateWebSocketMessage(sameTimestampTradeMessage); // Duplicate timestamp - should be skipped
        simulateWebSocketMessage(laterTradeMessage);       // Later trade - processed

        // Assert
        ArgumentCaptor<Trade> tradeCaptor = ArgumentCaptor.forClass(Trade.class);
        verify(mockTradeHandler, times(2)).accept(tradeCaptor.capture());
        
        // We should only have the first and third trade (IDs 12345 and 12347)
        List<String> capturedTradeIds = tradeCaptor.getAllValues().stream()
            .map(Trade::getTradeId)
            .collect(Collectors.toList());
        
        assertThat(capturedTradeIds).containsExactly("12345", "12347");
        assertThat(capturedTradeIds).doesNotContain("12346"); // Same timestamp trade is skipped
    }

    @Test
    public void handleMessage_acceptsTradesAfterStreamingIsStopped() {
        // Arrange
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        captureWebSocketListener();

        // First trade with timestamp t1
        String firstTradeMessage = """
            {
              "channel": "market_trades",
              "events": [{
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

        // Act - Send trade, stop streaming, then send another trade
        simulateWebSocketMessage(firstTradeMessage);
        
        // Stop streaming and clear timestamp tracking
        client.stopStreaming();
        
        // Second trade with EARLIER timestamp (should now be accepted since tracking was reset)
        String earlierTradeAfterReset = """
            {
              "channel": "market_trades",
              "events": [{
                "trades": [{
                  "trade_id": "12346",
                  "product_id": "BTC-USD",
                  "price": "50780",
                  "size": "0.00620",
                  "time": "2024-12-07T09:48:30.810058685Z" 
                }]
              }]
            }
            """;
        
        // Restart streaming
        client.startStreaming(TEST_PAIRS, mockTradeHandler);
        captureWebSocketListener();
        
        // Send the earlier trade (should now be processed since tracking was reset)
        simulateWebSocketMessage(earlierTradeAfterReset);

        // Assert - Both trades should be processed
        ArgumentCaptor<Trade> tradeCaptor = ArgumentCaptor.forClass(Trade.class);
        verify(mockTradeHandler, times(2)).accept(tradeCaptor.capture());
        
        List<String> capturedTradeIds = tradeCaptor.getAllValues().stream()
            .map(Trade::getTradeId)
            .collect(Collectors.toList());
        
        assertThat(capturedTradeIds).containsExactly("12345", "12346");
    }

    private void captureWebSocketListener() {
        verify(mockWebSocketBuilder).buildAsync(any(), listenerCaptor.capture());
    }

    private void simulateWebSocketMessage(String message) {
        listenerCaptor.getValue().onText(mockWebSocket, message, true);
    }
}
