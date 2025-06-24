package com.verlumen.tradestream.strategies.vpt;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.VptParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class VptParamConfigTest {

  private final VptParamConfig config = new VptParamConfig();

  @Test
  public void getChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<?> specs = config.getChromosomeSpecs();

    assertThat(specs).hasSize(1);
  }

  @Test
  public void initialChromosomes_returnsExpectedChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    assertThat(chromosomes).hasSize(1);
    assertThat(chromosomes.get(0)).isInstanceOf(IntegerChromosome.class);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsCorrectParameters()
      throws InvalidProtocolBufferException {
    // Create test chromosome
    IntegerChromosome periodChromosome = IntegerChromosome.of(10, 50, 25);

    ImmutableList<NumericChromosome<?, ?>> chromosomes = ImmutableList.of(periodChromosome);

    Any result = config.createParameters(chromosomes);

    assertThat(result.is(VptParameters.class)).isTrue();
    VptParameters parameters = result.unpack(VptParameters.class);
    assertThat(parameters.getPeriod()).isAtLeast(10);
    assertThat(parameters.getPeriod()).isAtMost(50);
  }

  @Test
  public void createParameters_withInvalidChromosomeCount_returnsDefaultParameters()
      throws InvalidProtocolBufferException {
    // Create empty chromosome list
    ImmutableList<NumericChromosome<?, ?>> chromosomes = ImmutableList.of();

    Any result = config.createParameters(chromosomes);

    assertThat(result.is(VptParameters.class)).isTrue();
    VptParameters parameters = result.unpack(VptParameters.class);
    assertThat(parameters.getPeriod()).isEqualTo(20);
  }
}
