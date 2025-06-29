package com.verlumen.tradestream.strategies.rainbowoscillator;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.RainbowOscillatorParameters;
import io.jenetics.IntegerChromosome;
import org.junit.Test;

public final class RainbowOscillatorParamConfigTest {
  private final RainbowOscillatorParamConfig paramConfig = new RainbowOscillatorParamConfig();

  @Test
  public void getChromosomeSpecs_returnsCorrectSpecs() {
    // Act
    var specs = paramConfig.getChromosomeSpecs();

    // Assert
    assertThat(specs).hasSize(3);
  }

  @Test
  public void initialChromosomes_returnsCorrectNumberOfChromosomes() {
    // Act
    var chromosomes = paramConfig.initialChromosomes();

    // Assert
    assertThat(chromosomes).hasSize(3);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsValidParameters()
      throws InvalidProtocolBufferException {
    // Arrange
    ImmutableList<IntegerChromosome> chromosomes =
        ImmutableList.of(
            IntegerChromosome.of(5, 20, 10), // min=5, max=20, value=10
            IntegerChromosome.of(10, 50, 25), // min=10, max=50, value=25
            IntegerChromosome.of(20, 100, 60) // min=20, max=100, value=60
            );

    // Act
    Any result = paramConfig.createParameters(chromosomes);

    // Assert
    assertThat(result).isNotNull();
    RainbowOscillatorParameters parameters = result.unpack(RainbowOscillatorParameters.class);
    assertThat(parameters.getPeriodsCount()).isEqualTo(3);
    assertThat(parameters.getPeriods(0)).isAtLeast(5);
    assertThat(parameters.getPeriods(0)).isAtMost(20);
    assertThat(parameters.getPeriods(1)).isAtLeast(10);
    assertThat(parameters.getPeriods(1)).isAtMost(50);
    assertThat(parameters.getPeriods(2)).isAtLeast(20);
    assertThat(parameters.getPeriods(2)).isAtMost(100);
  }

  @Test
  public void createParameters_withEmptyChromosomes_returnsDefaultParameters()
      throws InvalidProtocolBufferException {
    // Arrange
    ImmutableList<IntegerChromosome> chromosomes = ImmutableList.of();

    // Act
    Any result = paramConfig.createParameters(chromosomes);

    // Assert
    assertThat(result).isNotNull();
    RainbowOscillatorParameters parameters = result.unpack(RainbowOscillatorParameters.class);
    assertThat(parameters.getPeriodsCount()).isEqualTo(3);
    assertThat(parameters.getPeriods(0)).isEqualTo(10);
    assertThat(parameters.getPeriods(1)).isEqualTo(20);
    assertThat(parameters.getPeriods(2)).isEqualTo(50);
  }
}
