package com.verlumen.tradestream.strategies.renkochart;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.RenkoChartParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class RenkoChartParamConfigTest {

  private RenkoChartParamConfig config;

  @Before
  public void setUp() {
    config = new RenkoChartParamConfig();
  }

  @Test
  public void getChromosomeSpecs_returnsOneSpec() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();

    assertThat(specs).hasSize(1);
  }

  @Test
  public void getChromosomeSpecs_brickSizeSpec_hasCorrectMinimum() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    ChromosomeSpec<?> brickSizeSpec = specs.get(0);

    assertThat(brickSizeSpec.getRange().lowerEndpoint()).isEqualTo(0.1);
  }

  @Test
  public void getChromosomeSpecs_brickSizeSpec_hasCorrectMaximum() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    ChromosomeSpec<?> brickSizeSpec = specs.get(0);

    assertThat(brickSizeSpec.getRange().upperEndpoint()).isEqualTo(100.0);
  }

  @Test
  public void getChromosomeSpecs_createsDoubleChromosome() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    NumericChromosome<?, ?> chromosome = specs.get(0).createChromosome();

    assertThat(chromosome).isInstanceOf(DoubleChromosome.class);
  }

  @Test
  public void initialChromosomes_returnsOneChromosome() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    assertThat(chromosomes).hasSize(1);
  }

  @Test
  public void initialChromosomes_returnsDoubleChromosome() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    assertThat(chromosomes.get(0)).isInstanceOf(DoubleChromosome.class);
  }

  @Test
  public void initialChromosomes_valueIsWithinRange() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    DoubleChromosome chromosome = (DoubleChromosome) chromosomes.get(0);
    double value = chromosome.gene().allele();

    assertThat(value).isAtLeast(0.1);
    assertThat(value).isAtMost(100.0);
  }

  @Test
  public void createParameters_returnsPackedAny() throws InvalidProtocolBufferException {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    Any packed = config.createParameters(chromosomes);

    assertThat(packed.is(RenkoChartParameters.class)).isTrue();
  }

  @Test
  public void createParameters_unpacksToRenkoChartParameters()
      throws InvalidProtocolBufferException {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    Any packed = config.createParameters(chromosomes);
    RenkoChartParameters params = packed.unpack(RenkoChartParameters.class);

    assertThat(params).isNotNull();
  }

  @Test
  public void createParameters_extractsBrickSize() throws InvalidProtocolBufferException {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    double expectedValue = ((DoubleChromosome) chromosomes.get(0)).gene().allele();

    Any packed = config.createParameters(chromosomes);
    RenkoChartParameters params = packed.unpack(RenkoChartParameters.class);

    assertThat(params.getBrickSize()).isWithin(0.0001).of(expectedValue);
  }

  @Test
  public void createParameters_withEmptyList_usesMinBrickSize()
      throws InvalidProtocolBufferException {
    ImmutableList<NumericChromosome<?, ?>> empty = ImmutableList.of();

    Any packed = config.createParameters(empty);
    RenkoChartParameters params = packed.unpack(RenkoChartParameters.class);

    assertThat(params.getBrickSize()).isWithin(0.0001).of(0.1);
  }

  @Test
  public void createParameters_brickSizeIsPositive() throws InvalidProtocolBufferException {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    Any packed = config.createParameters(chromosomes);
    RenkoChartParameters params = packed.unpack(RenkoChartParameters.class);

    assertThat(params.getBrickSize()).isGreaterThan(0.0);
  }

  @Test
  public void getChromosomeSpecs_returnsSameInstanceOnMultipleCalls() {
    ImmutableList<ChromosomeSpec<?>> specs1 = config.getChromosomeSpecs();
    ImmutableList<ChromosomeSpec<?>> specs2 = config.getChromosomeSpecs();

    assertThat(specs1).isSameInstanceAs(specs2);
  }

  @Test
  public void initialChromosomes_createsNewInstancesEachCall() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes1 = config.initialChromosomes();
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes2 = config.initialChromosomes();

    assertThat(chromosomes1).isNotSameInstanceAs(chromosomes2);
  }

  @Test
  public void brickSizeRange_isReasonableForTrading() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    ChromosomeSpec<?> brickSizeSpec = specs.get(0);

    // Minimum brick size should be small but positive
    assertThat((Double) brickSizeSpec.getRange().lowerEndpoint()).isGreaterThan(0.0);

    // Maximum brick size should be reasonable for most assets
    assertThat((Double) brickSizeSpec.getRange().upperEndpoint()).isGreaterThan(1.0);
    assertThat((Double) brickSizeSpec.getRange().upperEndpoint()).isLessThan(1000.0);
  }
}
