package com.verlumen.tradestream.marketdata;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.Provider;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.instruments.CurrencyPairSupply;
import java.io.IOException;
import java.util.List;
import javax.annotation.Nullable;
import org.apache.beam.sdk.coders.Coder;
import org.apache.beam.sdk.coders.SerializableCoder;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.io.UnboundedSource;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.values.TypeDescriptor;
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

  @Rule
  public final MockitoRule mockito = MockitoJUnit.rule();

  // Mocks for dependencies injected into the source
  @Mock
  @Bind
  private ExchangeClientUnboundedReader.Factory mockReaderFactory;

  @Mock
  @Bind
  private Provider<CurrencyPairSupply> mockCurrencyPairSupplyProvider;

  // Mocks returned by the dependencies
  @Mock
  private ExchangeClientUnboundedReader mockReader;

  @Mock
  private CurrencyPairSupply mockCurrencyPairSupply;

  // Instance under test
  @Inject
  private ExchangeClientUnboundedSourceImpl source;

  private PipelineOptions pipelineOptions;

  @Before
  public void setUp() {
    // Configure the provider mock
    when(mockCurrencyPairSupplyProvider.get()).thenReturn(mockCurrencyPairSupply);

    // Configure the reader factory mock
    when(mockReaderFactory.create(
        any(ExchangeClientUnboundedSource.class),
        any(CurrencyPairSupply.class),
        any(TradeCheckpointMark.class)))
        .thenReturn(mockReader);

    // Inject dependencies
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);

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
    @Nullable TradeCheckpointMark nullCheckpointMark = null;

    // Act
    UnboundedSource.UnboundedReader<Trade> reader =
        source.createReader(pipelineOptions, nullCheckpointMark);

    // Assert
    verify(mockCurrencyPairSupplyProvider).get(); // Verify provider was called
    verify(mockReaderFactory).create(eq(source), eq(mockCurrencyPairSupply), eq(TradeCheckpointMark.INITIAL));
    assertThat(reader).isSameInstanceAs(mockReader);
  }

  @Test
  public void createReader_withNonNullCheckpoint_callsFactoryWithProvidedMark() throws IOException {
    // Arrange
    TradeCheckpointMark specificMark = new TradeCheckpointMark(Instant.ofEpochMilli(12345L));

    // Act
    UnboundedSource.UnboundedReader<Trade> reader =
        source.createReader(pipelineOptions, specificMark);

    // Assert
    verify(mockCurrencyPairSupplyProvider).get(); // Verify provider was called
    verify(mockReaderFactory).create(eq(source), eq(mockCurrencyPairSupply), eq(specificMark));
    assertThat(reader).isSameInstanceAs(mockReader);
  }

  // --- getCheckpointMarkCoder() Tests ---

  @Test
  public void getCheckpointMarkCoder_returnsSerializableCoder() {
    // Arrange (Implicit setup)

    // Act
    Coder<TradeCheckpointMark> coder = source.getCheckpointMarkCoder();

    // Assert
    assertThat(coder).isInstanceOf(SerializableCoder.class);
  }

  @Test
  public void getCheckpointMarkCoder_returnsCoderForTradeCheckpointMark() {
    // Arrange (Implicit setup)

    // Act
    Coder<TradeCheckpointMark> coder = source.getCheckpointMarkCoder();

    // Assert
    assertThat(coder.getEncodedTypeDescriptor())
        .isEqualTo(TypeDescriptor.of(TradeCheckpointMark.class));
  }

  // --- getOutputCoder() Tests ---

  @Test
  public void getOutputCoder_returnsProtoCoder() {
    // Arrange (Implicit setup)

    // Act
    Coder<Trade> coder = source.getOutputCoder();

    // Assert
    assertThat(coder).isInstanceOf(ProtoCoder.class);
  }

  @Test
  public void getOutputCoder_returnsCoderForTrade() {
    // Arrange (Implicit setup)

    // Act
    Coder<Trade> coder = source.getOutputCoder();

    // Assert
    assertThat(coder.getEncodedTypeDescriptor()).isEqualTo(TypeDescriptor.of(Trade.class));
  }
}
