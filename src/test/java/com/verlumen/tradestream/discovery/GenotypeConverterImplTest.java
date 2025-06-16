package com.verlumen.tradestream.discovery;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.DoubleChromosome;
import io.jenetics.DoubleGene;
import io.jenetics.Genotype;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class GenotypeConverterImplTest {
  @Rule public MockitoRule rule = MockitoJUnit.rule();

  // This test no longer needs to mock ParamConfig since we are testing the real implementation path.
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

    // Create a Genotype with specific allele values that match the expected structure of SmaRsiParameters.
    Genotype<?> genotype =
        Genotype.of(
            IntegerChromosome.of(10, 10), // movingAveragePeriod
            IntegerChromosome.of(14, 14), // rsiPeriod
            DoubleChromosome.of(70.0, 70.0), // overboughtThreshold
            DoubleChromosome.of(30.0, 30.0) // oversoldThreshold
            );

    // Act
    Any actualParameters = converter.convertToParameters(genotype, strategyType);

    // Assert
    // Verify the packed message is of the correct type.
    assertThat(actualParameters.is(SmaRsiParameters.class)).isTrue();
    SmaRsiParameters unpackedParams = actualParameters.unpack(SmaRsiParameters.class);

    // Verify the parameters were set correctly from the genotype's alleles.
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
    Genotype<DoubleGene> genotype = Genotype.of(DoubleChromosome.of(0.0, 1.0));

    // Act & Assert
    assertThrows(NullPointerException.class, () -> converter.convertToParameters(genotype, null));
  }

  @Test
  public void createParameters_invalidChromosomeSize_throwsException() {
    // Arrange: Create a genotype with fewer chromosomes than the strategy expects.
    Genotype<?> genotypeWithWrongSize =
        Genotype.of(
            IntegerChromosome.of(10, 10),
            IntegerChromosome.of(14, 14));

    // Act & Assert: This should throw an exception from within SmaRsiParamConfig, which is the
    // expected behavior for a fundamental mismatch.
    assertThrows(
        IllegalArgumentException.class,
        () -> converter.convertToParameters(genotypeWithWrongSize, StrategyType.SMA_RSI));
  }
}
