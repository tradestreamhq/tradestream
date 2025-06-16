package com.verlumen.tradestream.discovery;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import io.jenetics.Genotype;
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

    // Create the individual chromosomes of different types.
    IntegerChromosome maPeriodChromosome = IntegerChromosome.of(10, 10);
    IntegerChromosome rsiPeriodChromosome = IntegerChromosome.of(14, 14);
    DoubleChromosome overboughtChromosome = DoubleChromosome.of(70.0, 70.0);
    DoubleChromosome oversoldChromosome = DoubleChromosome.of(30.0, 30.0);

    // Create a list of these mixed-type chromosomes.
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            maPeriodChromosome, rsiPeriodChromosome, overboughtChromosome, oversoldChromosome);

    // Mock the Genotype to behave as if it contains our mixed list.
    Genotype mockGenotype = mock(Genotype.class);
    when(mockGenotype.iterator()).thenReturn(chromosomes.iterator());

    // Act
    Any actualParameters = converter.convertToParameters(mockGenotype, strategyType);

    // Assert
    // Check that the returned Any object contains the correct parameter type.
    assertThat(actualParameters.is(SmaRsiParameters.class)).isTrue();

    // Unpack the parameters to verify the values.
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

  @Test
  public void createParameters_invalidChromosomeSize_throwsException() {
    // Arrange: Create a Genotype with a number of chromosomes that does not match
    // what SmaRsiParamConfig expects (it expects 4).
    Genotype<?> genotypeWithWrongSize =
        Genotype.of(
            IntegerChromosome.of(10, 50),
            IntegerChromosome.of(2, 30));

    // Act & Assert
    // This should throw an exception from within SmaRsiParamConfig, which is the
    // expected behavior for a fundamental mismatch. The converter should let this bubble up.
    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class,
            () -> converter.convertToParameters(genotypeWithWrongSize, StrategyType.SMA_RSI));

    assertThat(thrown).hasMessageThat().contains("Expected 4 chromosomes but got 2");
  }
}
