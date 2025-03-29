package com.verlumen.tradestream.marketdata;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.Injector;
import com.google.inject.Provider;
import com.google.inject.assistedinject.FactoryModuleBuilder;
import com.google.protobuf.Timestamp;
import com.google.protobuf.util.Timestamps;
import com.verlumen.tradestream.instruments.CurrencyPair;
import com.verlumen.tradestream.instruments.CurrencyPairSupply;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.function.Consumer;
import org.apache.beam.sdk.coders.Coder;
import org.apache.beam.sdk.coders.SerializableCoder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.io.UnboundedSource;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.joda.time.Instant;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

/**
 * Unit tests for {@link ExchangeClientUnboundedSourceImpl}.
 */
@RunWith(JUnit4.class)
public class ExchangeClientUnboundedSourceImplTest {

  // We still need to mock the currency pair supply
  @Mock
  private CurrencyPairSupply mockCurrencyPairSupply;
  
  // Mockito rule to initialize mocks
  @Rule
  public MockitoRule mockitoRule = MockitoJUnit.rule();
  
  // Test currency pairs
  private final ImmutableList<CurrencyPair> TEST_PAIRS = ImmutableList.of(
      CurrencyPair.fromSymbol("BTC/USD")
  );
  
  // Our fake client instance
  private FakeExchangeStreamingClient fakeClient;
  
  // Instance under test
  private ExchangeClientUnboundedSourceImpl source;
  private PipelineOptions pipelineOptions;

  @Before
  public void setUp() {
    // Configure mock
    when(mockCurrencyPairSupply.currencyPairs()).thenReturn(TEST_PAIRS);
    
    // Create our fake client
    fakeClient = new FakeExchangeStreamingClient();
    
    // Create a provider for our currency pair supply
    Provider<CurrencyPairSupply> currencyPairSupplyProvider = () -> mockCurrencyPairSupply;
    
    // Create an injector with our test dependencies
    Injector injector = Guice.createInjector(new AbstractModule() {
      @Override
      protected void configure() {
        // Bind the exchange client to our fake implementation
        bind(ExchangeStreamingClient.class).toInstance(fakeClient);
        
        // Install the factory module for creating readers
        install(new FactoryModuleBuilder()
            .implement(ExchangeClientUnboundedReader.class, ExchangeClientUnboundedReader.class)
            .build(ExchangeClientUnboundedReader.Factory.class));
      }
    });

    // Use Guice to inject dependencies
    source = injector.getInstance(ExchangeClientUnboundedSourceImpl.class);

    // Create default pipeline options
    pipelineOptions = PipelineOptionsFactory.create();
  }

  // --- split() Tests ---

  @Test
  public void split_returnsSingletonListContainingSelf() throws Exception {
    // Arrange
    int desiredNumSplits = 5; // Example value, shouldn't affect outcome

    // Act
    List<UnboundedSource<Trade, TradeCheckpointMark>> splits =
        source.split(desiredNumSplits, pipelineOptions);

    // Assert
    assertThat(splits).containsExactly(source);
  }

  // --- createReader() Tests ---

  @Test
  public void createReader_withNullCheckpoint_callsFactoryWithInitialMark() throws IOException {
    // Arrange
    TradeCheckpointMark nullCheckpointMark = null;

    // Act
    UnboundedSource.UnboundedReader<Trade> reader =
        source.createReader(pipelineOptions, nullCheckpointMark);
    
    // Queue a trade before starting the reader
    Instant now = Instant.now();
    Trade trade = fakeClient.createTrade("test1", now);
    fakeClient.queueTrade(trade);
    
    // Start the reader to activate the fake client
    boolean hasData = reader.start();
    
    // Assert
    assertThat(hasData).isTrue();
    assertThat(reader.getCurrent().getTradeId()).isEqualTo("test1");

    // Cleanup
    reader.close();
  }

  @Test
  public void createReader_withNonNullCheckpoint_callsFactoryWithProvidedMark() throws IOException {
    // Arrange
    Instant specificTimestamp = Instant.ofEpochMilli(12345L);
    TradeCheckpointMark specificMark = new TradeCheckpointMark(specificTimestamp);

    // Queue trades before creating reader
    Trade beforeTrade = fakeClient.createTrade("before", specificTimestamp.minus(1000));
    Trade afterTrade = fakeClient.createTrade("after", specificTimestamp.plus(1000));
    
    fakeClient.queueTrade(beforeTrade);
    fakeClient.queueTrade(afterTrade);
    
    // Act
    UnboundedSource.UnboundedReader<Trade> reader =
        source.createReader(pipelineOptions, specificMark);
    
    // Start the reader - should return true since we have at least one valid trade
    boolean hasData = reader.start();
    
    // Assert
    assertThat(hasData).isTrue();
    // Should have advanced to the "after" trade and skipped the "before" trade
    assertThat(reader.getCurrent().getTradeId()).isEqualTo("after");

    // Cleanup
    reader.close();
  }

  // --- getCheckpointMarkCoder() Tests ---

  @Test
  public void getCheckpointMarkCoder_returnsSerializableCoder() {
    // Act
    Coder<TradeCheckpointMark> coder = source.getCheckpointMarkCoder();

    // Assert
    assertThat(coder).isInstanceOf(SerializableCoder.class);
  }

  // --- getOutputCoder() Tests ---

  @Test
  public void getOutputCoder_returnsProtoCoder() {
    // Act
    Coder<Trade> coder = source.getOutputCoder();

    // Assert
    assertThat(coder).isInstanceOf(ProtoCoder.class);
    // Additional check to verify it's for Trade class
    ProtoCoder<?> protoCoder = (ProtoCoder<?>) coder;
    assertThat(protoCoder.toString()).contains("Trade");
  }

  @Test
  public void getOutputCoder_returnsCoderForTrade() {
    // Act
    Coder<Trade> coder = source.getOutputCoder();

    // Assert
    // ProtoCoder actually returns Message.class as raw type since Trade is a Protocol Buffer
    assertThat(coder).isInstanceOf(ProtoCoder.class);
  }

  /**
   * A fake implementation of ExchangeStreamingClient for testing.
   */
  static class FakeExchangeStreamingClient implements ExchangeStreamingClient {
    private Consumer<Trade> tradeCallback;
    private final LinkedBlockingQueue<Trade> queuedTrades = new LinkedBlockingQueue<>();
    private boolean isStreaming = false;
    private ImmutableList<CurrencyPair> subscribedPairs;

    @Override
    public void startStreaming(ImmutableList<CurrencyPair> currencyPairs, Consumer<Trade> callback) {
      this.subscribedPairs = currencyPairs;
      this.tradeCallback = callback;
      this.isStreaming = true;
      
      // Process any queued trades
      List<Trade> tradesToProcess = new ArrayList<>();
      queuedTrades.drainTo(tradesToProcess);
      for (Trade trade : tradesToProcess) {
        callback.accept(trade);
      }
    }

    @Override
    public void stopStreaming() {
      this.isStreaming = false;
    }
    
    @Override
    public ImmutableList<CurrencyPair> supportedCurrencyPairs() {
      return subscribedPairs != null ? subscribedPairs : ImmutableList.of();
    }
    
    @Override
    public String getExchangeName() {
      return "FakeExchange";
    }

    public void queueTrade(Trade trade) {
      if (isStreaming && tradeCallback != null) {
        tradeCallback.accept(trade);
      } else {
        queuedTrades.add(trade);
      }
    }

    public Trade createTrade(String id, Instant timestamp) {
      Timestamp protoTimestamp = Timestamps.fromMillis(timestamp.getMillis());
      
      return Trade.newBuilder()
          .setTradeId(id)
          .setPrice(1000.0)
          // Use volume instead of quantity
          .setVolume(1.0)
          .setTimestamp(protoTimestamp)
          .build();
    }
  }
}
