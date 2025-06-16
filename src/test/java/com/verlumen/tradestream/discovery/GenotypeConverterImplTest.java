package com.verlumen.tradestream.discovery;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.mock;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.Chromosome;
import io.jenetics.DoubleChromosome;
import io.jenetics.Genotype;
import io.jenetics.IntegerChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class GenotypeConverterImplTest {
  @Rule public MockitoRule rule = MockitoJUnit.rule();

  @Inject private GenotypeConverterImpl converter;

  @Before
  public void setUp() {
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  @Test
  public void convertToParameters_validGenotype_returnsCorrectParameters()
      throws InvalidProtocolBufferException {
    // Arrange
    StrategyType strategyType = StrategyType.SMA_RSI;

    // Create the individual chromosomes with valid ranges where min < max.
    IntegerChromosome maPeriodChromosome = IntegerChromosome.of(10, 11); // -> 10
    IntegerChromosome rsiPeriodChromosome = IntegerChromosome.of(14, 15); // -> 14
    DoubleChromosome overboughtChromosome = DoubleChromosome.of(70.0, 70.1); // -> 70.0
    DoubleChromosome oversoldChromosome = DoubleChromosome.of(30.0, 30.1); // -> 30.0

    // Use the more general Chromosome<?> type for the list.
    List<Chromosome<?>> chromosomes =
        List.of(
            maPeriodChromosome, rsiPeriodChromosome, overboughtChromosome, oversoldChromosome);

    // Mock the Genotype to behave as if it contains our mixed list.
    // Use the doReturn(...).when(...) syntax to avoid generics issues with Mockito.
    Genotype<?> mockGenotype = mock(Genotype.class);
    doReturn(chromosomes.iterator()).when(mockGenotype).iterator();

    // Act
    Any actualParameters = converter.convertToParameters(mockGenotype, strategyType);

    // Assert
    assertThat(actualParameters.is(SmaRsiParameters.class)).isTrue();

    SmaRsiParameters unpackedParams = actualParameters.unpack(SmaRsiParameters.class);
    assertThat(unpackedParams.getMovingAveragePeriod()).isEqualTo(10);
    assertThat(unpackedParams.getRsiPeriod()).isEqualTo(14);
    assertThat(unpackedParams.getOverboughtThreshold()).isEqualTo(70.0);
    assertThat(unpackedParams.getOversoldThreshold()).isEqualTo(30.0);
  }

  @Test
  public void convertToParameters_nullGenotype_throwsNullPointerException() {
    // Arrange
    StrategyType strategyType = StrategyType.SMA_RSI;

    // Act & Assert
    assertThrows(NullPointerException.class, () -> converter.convertToParameters(null, strategyType));
  }

  @Test
  public void convertToParameters_nullStrategyType_throwsNullPointerException() {
    // Arrange
    Genotype<?> genotype = Genotype.of(DoubleChromosome.of(0, 1));

    // Act & Assert
    assertThrows(NullPointerException.class, () -> converter.convertToParameters(genotype, null));
  }
}
