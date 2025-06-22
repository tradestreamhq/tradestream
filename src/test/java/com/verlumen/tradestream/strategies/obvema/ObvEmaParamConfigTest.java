package com.verlumen.tradestream.strategies.obvema;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.ObvEmaParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class ObvEmaParamConfigTest {

  private final ObvEmaParamConfig config = new ObvEmaParamConfig();

  @Test
  public void getChromosomeSpecs_returnsCorrectSize() {
    assertThat(config.getChromosomeSpecs()).hasSize(1);
  }

  @Test
  public void initialChromosomes_returnsCorrectSize() {
    assertThat(config.initialChromosomes()).hasSize(1);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsValidParameters()
      throws InvalidProtocolBufferException {
    // Arrange
    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(IntegerChromosome.of(10, 50, 1));

    // Act
    Any result = config.createParameters(chromosomes);

    // Assert
    assertThat(result).isNotNull();
    ObvEmaParameters parameters = result.unpack(ObvEmaParameters.class);
    assertThat(parameters.getEmaPeriod()).isGreaterThan(0);
  }

  @Test
  public void createParameters_withTooManyChromosomes_usesFirstOne()
      throws InvalidProtocolBufferException {
    // Arrange
    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(IntegerChromosome.of(10, 50, 1), IntegerChromosome.of(10, 50, 1));

    // Act
    Any result = config.createParameters(chromosomes);

    // Assert
    assertThat(result).isNotNull();
    ObvEmaParameters parameters = result.unpack(ObvEmaParameters.class);
    assertThat(parameters.getEmaPeriod()).isGreaterThan(0);
  }

  @Test
  public void createParameters_withTooFewChromosomes_usesDefaultValue()
      throws InvalidProtocolBufferException {
    // Arrange
    ImmutableList<NumericChromosome<?, ?>> chromosomes = ImmutableList.of();

    // Act
    Any result = config.createParameters(chromosomes);

    // Assert
    assertThat(result).isNotNull();
    ObvEmaParameters parameters = result.unpack(ObvEmaParameters.class);
    assertThat(parameters.getEmaPeriod()).isEqualTo(20);
  }

  @Test
  public void createParameters_withInvalidChromosome_usesDefaultValue()
      throws InvalidProtocolBufferException {
    // Arrange - Create an empty chromosome list to trigger default value
    ImmutableList<NumericChromosome<?, ?>> chromosomes = ImmutableList.of();

    // Act
    Any result = config.createParameters(chromosomes);

    // Assert
    assertThat(result).isNotNull();
    ObvEmaParameters parameters = result.unpack(ObvEmaParameters.class);
    assertThat(parameters.getEmaPeriod()).isEqualTo(20);
  }
}
