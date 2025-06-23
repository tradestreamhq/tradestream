package com.verlumen.tradestream.strategies.doubletopbottom;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DoubleTopBottomParameters;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class DoubleTopBottomParamConfigTest {

  private final DoubleTopBottomParamConfig paramConfig = new DoubleTopBottomParamConfig();

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
    var chromosome = paramConfig.getChromosomeSpecs().get(0).createChromosome();
    var chromosomes = ImmutableList.of(chromosome);

    // Act
    Any result = paramConfig.createParameters(chromosomes);

    // Assert
    DoubleTopBottomParameters parameters = result.unpack(DoubleTopBottomParameters.class);
    assertThat(parameters.getPeriod())
        .isEqualTo(((NumericChromosome<Integer, ?>) chromosome).intValue());
  }

  @Test(expected = IllegalArgumentException.class)
  public void createParameters_withWrongNumberOfChromosomes_throwsException() {
    // Arrange
    var chromosome = paramConfig.getChromosomeSpecs().get(0).createChromosome();
    var chromosomes = ImmutableList.of(chromosome, chromosome);

    // Act
    paramConfig.createParameters(chromosomes);
  }
}
