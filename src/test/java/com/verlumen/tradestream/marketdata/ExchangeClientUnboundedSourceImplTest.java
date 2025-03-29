package com.verlumen.tradestream.marketdata;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.AbstractModule;
import com.google.inject.Guice;
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
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

/**
 * Unit tests for {@link ExchangeClientUnboundedSourceImpl}.
 */
@RunWith(JUnit4.class)
public class ExchangeClientUnboundedSourceImplTest {
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
          .setQuantity(1.0)
          .setTimestamp(protoTimestamp)
          .build();
    }
  }

  // Our fake client instance
  private FakeExchangeStreamingClient fakeClient;
  
  // We still need to mock the currency pair supply
  @Mock
  private CurrencyPairSupply mockCurrencyPairSupply;
  
  // Test currency pairs
  private final ImmutableList<CurrencyPair> TEST_PAIRS = ImmutableList.of(
      createCurrencyPair("BTC", "USD")
  );
  
  // Helper method to create CurrencyPair instances
  private CurrencyPair createCurrencyPair(String base, String quote) {
      CurrencyPair.Builder builder = CurrencyPair.newBuilder();
      builder.setBaseCurrency(base);
      builder.setQuoteCurrency(quote);
      return builder.build();
  }
  
  // Instance under test
  private ExchangeClientUnboundedSourceImpl source;
  private PipelineOptions pipelineOptions;

  @Before
  public void setUp() {
    MockitoAnnotations.initMocks(this);
    
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

    // Create the reader factory from our injector
    ExchangeClientUnboundedReader.Factory readerFactory = 
        injector.getInstance(ExchangeClientUnboundedReader.Factory.class);
    
    // Create the source instance
    source = new ExchangeClientUnboundedSourceImpl(
        readerFactory,
        currencyPairSupplyProvider
    );

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
    
    // Start the reader to activate the fake client
    reader.start();

    // Assert - verify the reader uses the INITIAL mark by queueing a trade after that mark
    Instant now = Instant.now();
    Trade trade = fakeClient.createTrade("test1", now);
    fakeClient.queueTrade(trade);
    
    // should have advanced to our trade
    assertThat(reader.getCurrent().getTradeId()).isEqualTo("test1");

    // Cleanup
    reader.close();
  }

  @Test
  public void createReader_withNonNullCheckpoint_callsFactoryWithProvidedMark() throws IOException {
    // Arrange
    Instant specificTimestamp = Instant.ofEpochMilli(12345L);
    TradeCheckpointMark specificMark = new TradeCheckpointMark(specificTimestamp);

    // Act
    UnboundedSource.UnboundedReader<Trade> reader =
        source.createReader(pipelineOptions, specificMark);
    
    // Start the reader
    reader.start();
    
    // Queue a trade before the checkpoint - should be ignored
    Trade beforeTrade = fakeClient.createTrade("before", specificTimestamp.minus(1000));
    fakeClient.queueTrade(beforeTrade);
    
    // Queue a trade after the checkpoint - should be processed
    Trade afterTrade = fakeClient.createTrade("after", specificTimestamp.plus(1000));
    fakeClient.queueTrade(afterTrade);
    
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
  }

  @Test
  public void getOutputCoder_returnsCoderForTrade() {
    // Act
    Coder<Trade> coder = source.getOutputCoder();

    // Assert
    assertThat(coder.getEncodedTypeDescriptor().getRawType()).isEqualTo(Trade.class);
  }
}
