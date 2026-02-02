package com.verlumen.tradestream.strategies.emamacd;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.EmaMacdParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class EmaMacdParamConfigTest {

  private EmaMacdParamConfig config;

  @Before
  public void setUp() {
    config = new EmaMacdParamConfig();
  }

  @Test
  public void getChromosomeSpecs_returnsThreeSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();

    assertThat(specs).hasSize(3);
  }

  @Test
  public void getChromosomeSpecs_allSpecsAreIntegerType() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();

    for (ChromosomeSpec<?> spec : specs) {
      NumericChromosome<?, ?> chromosome = spec.createChromosome();
      assertThat(chromosome).isInstanceOf(IntegerChromosome.class);
    }
  }

  @Test
  public void getChromosomeSpecs_shortEmaPeriodSpec_hasCorrectRange() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    ChromosomeSpec<?> shortEmaPeriodSpec = specs.get(0);

    assertThat(shortEmaPeriodSpec.getRange().lowerEndpoint()).isEqualTo(2);
    assertThat(shortEmaPeriodSpec.getRange().upperEndpoint()).isEqualTo(20);
  }

  @Test
  public void getChromosomeSpecs_longEmaPeriodSpec_hasCorrectRange() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    ChromosomeSpec<?> longEmaPeriodSpec = specs.get(1);

    assertThat(longEmaPeriodSpec.getRange().lowerEndpoint()).isEqualTo(10);
    assertThat(longEmaPeriodSpec.getRange().upperEndpoint()).isEqualTo(50);
  }

  @Test
  public void getChromosomeSpecs_signalPeriodSpec_hasCorrectRange() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    ChromosomeSpec<?> signalPeriodSpec = specs.get(2);

    assertThat(signalPeriodSpec.getRange().lowerEndpoint()).isEqualTo(5);
    assertThat(signalPeriodSpec.getRange().upperEndpoint()).isEqualTo(20);
  }

  @Test
  public void initialChromosomes_returnsThreeChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    assertThat(chromosomes).hasSize(3);
  }

  @Test
  public void initialChromosomes_allAreIntegerChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    for (NumericChromosome<?, ?> chromosome : chromosomes) {
      assertThat(chromosome).isInstanceOf(IntegerChromosome.class);
    }
  }

  @Test
  public void initialChromosomes_valuesAreWithinRange() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    for (int i = 0; i < chromosomes.size(); i++) {
      IntegerChromosome chromosome = (IntegerChromosome) chromosomes.get(i);
      int value = chromosome.gene().allele();
      int min = (Integer) specs.get(i).getRange().lowerEndpoint();
      int max = (Integer) specs.get(i).getRange().upperEndpoint();

      assertThat(value).isAtLeast(min);
      assertThat(value).isAtMost(max);
    }
  }

  @Test
  public void createParameters_returnsPackedAny() throws InvalidProtocolBufferException {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    Any packed = config.createParameters(chromosomes);

    assertThat(packed.is(EmaMacdParameters.class)).isTrue();
  }

  @Test
  public void createParameters_unpacksToEmaMacdParameters() throws InvalidProtocolBufferException {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    Any packed = config.createParameters(chromosomes);
    EmaMacdParameters params = packed.unpack(EmaMacdParameters.class);

    assertThat(params).isNotNull();
  }

  @Test
  public void createParameters_extractsShortEmaPeriod() throws InvalidProtocolBufferException {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    int expectedValue = ((IntegerChromosome) chromosomes.get(0)).gene().allele();

    Any packed = config.createParameters(chromosomes);
    EmaMacdParameters params = packed.unpack(EmaMacdParameters.class);

    assertThat(params.getShortEmaPeriod()).isEqualTo(expectedValue);
  }

  @Test
  public void createParameters_extractsLongEmaPeriod() throws InvalidProtocolBufferException {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    int expectedValue = ((IntegerChromosome) chromosomes.get(1)).gene().allele();

    Any packed = config.createParameters(chromosomes);
    EmaMacdParameters params = packed.unpack(EmaMacdParameters.class);

    assertThat(params.getLongEmaPeriod()).isEqualTo(expectedValue);
  }

  @Test
  public void createParameters_extractsSignalPeriod() throws InvalidProtocolBufferException {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    int expectedValue = ((IntegerChromosome) chromosomes.get(2)).gene().allele();

    Any packed = config.createParameters(chromosomes);
    EmaMacdParameters params = packed.unpack(EmaMacdParameters.class);

    assertThat(params.getSignalPeriod()).isEqualTo(expectedValue);
  }

  @Test
  public void createParameters_withWrongChromosomeCount_throwsException() {
    ImmutableList<NumericChromosome<?, ?>> twoChromosomes =
        ImmutableList.of(IntegerChromosome.of(2, 20), IntegerChromosome.of(10, 50));

    IllegalArgumentException exception =
        assertThrows(
            IllegalArgumentException.class, () -> config.createParameters(twoChromosomes));

    assertThat(exception.getMessage()).contains("Expected 3 chromosomes but got 2");
  }

  @Test
  public void createParameters_withEmptyList_throwsException() {
    ImmutableList<NumericChromosome<?, ?>> empty = ImmutableList.of();

    IllegalArgumentException exception =
        assertThrows(IllegalArgumentException.class, () -> config.createParameters(empty));

    assertThat(exception.getMessage()).contains("Expected 3 chromosomes but got 0");
  }

  @Test
  public void getChromosomeSpecs_returnsSameInstanceOnMultipleCalls() {
    ImmutableList<ChromosomeSpec<?>> specs1 = config.getChromosomeSpecs();
    ImmutableList<ChromosomeSpec<?>> specs2 = config.getChromosomeSpecs();

    assertThat(specs1).isSameInstanceAs(specs2);
  }
}
