package com.verlumen.tradestream.strategies.dematemacrossover;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DemaTemaCrossoverParameters;
import io.jenetics.IntegerChromosome;
import org.junit.Test;

public final class DemaTemaCrossoverParamConfigTest {
  private final DemaTemaCrossoverParamConfig paramConfig = new DemaTemaCrossoverParamConfig();

  @Test
  public void getChromosomeSpecs_returnsCorrectSpecs() {
    // Act
    var specs = paramConfig.getChromosomeSpecs();

    // Assert
    assertThat(specs).hasSize(2);
  }

  @Test
  public void initialChromosomes_returnsCorrectNumberOfChromosomes() {
    // Act
    var chromosomes = paramConfig.initialChromosomes();

    // Assert
    assertThat(chromosomes).hasSize(2);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsCorrectParameters()
      throws InvalidProtocolBufferException {
    // Arrange
    IntegerChromosome demaPeriodChrom = IntegerChromosome.of(5, 50);
    IntegerChromosome temaPeriodChrom = IntegerChromosome.of(5, 50);
    ImmutableList<IntegerChromosome> chromosomes =
        ImmutableList.of(demaPeriodChrom, temaPeriodChrom);

    // Act
    Any result = paramConfig.createParameters(chromosomes);

    // Assert
    DemaTemaCrossoverParameters parameters = result.unpack(DemaTemaCrossoverParameters.class);
    assertThat(parameters.getDemaPeriod()).isEqualTo(demaPeriodChrom.gene().allele());
    assertThat(parameters.getTemaPeriod()).isEqualTo(temaPeriodChrom.gene().allele());
  }

  @Test(expected = IllegalArgumentException.class)
  public void createParameters_withWrongNumberOfChromosomes_throwsException() {
    // Arrange
    IntegerChromosome demaPeriodChrom = IntegerChromosome.of(5, 50);
    ImmutableList<IntegerChromosome> chromosomes = ImmutableList.of(demaPeriodChrom);

    // Act & Assert
    paramConfig.createParameters(chromosomes);
  }
}
