package com.verlumen.tradestream.strategies.fibonacciretracements;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.FibonacciRetracementsParameters;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class FibonacciRetracementsParamConfigTest {

  private final FibonacciRetracementsParamConfig paramConfig =
      new FibonacciRetracementsParamConfig();

  @Test
  public void getChromosomeSpecs_returnsCorrectSpecs() {
    // Act
    var specs = paramConfig.getChromosomeSpecs();

    // Assert
    assertThat(specs).hasSize(1);
    assertThat(specs.get(0).getRange().lowerEndpoint()).isEqualTo(10);
    assertThat(specs.get(0).getRange().upperEndpoint()).isEqualTo(50);
  }

  @Test
  public void initialChromosomes_returnsCorrectChromosomes() {
    // Act
    var chromosomes = paramConfig.initialChromosomes();

    // Assert
    assertThat(chromosomes).hasSize(1);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsCorrectParameters()
      throws InvalidProtocolBufferException {
    // Arrange
    var chromosomes = paramConfig.initialChromosomes();
    int expectedPeriod = ((NumericChromosome<Integer, ?>) chromosomes.get(0)).intValue();

    // Act
    Any result = paramConfig.createParameters(chromosomes);

    // Assert
    assertThat(result).isNotNull();
    FibonacciRetracementsParameters parameters =
        result.unpack(FibonacciRetracementsParameters.class);
    assertThat(parameters.getPeriod()).isEqualTo(expectedPeriod);
  }

  @Test(expected = IllegalArgumentException.class)
  public void createParameters_withEmptyChromosomes_throwsException() {
    // Act
    paramConfig.createParameters(ImmutableList.of());
  }
}
