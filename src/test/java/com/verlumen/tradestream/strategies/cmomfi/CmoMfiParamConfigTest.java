package com.verlumen.tradestream.strategies.cmomfi;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.CmoMfiParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class CmoMfiParamConfigTest {

  private final CmoMfiParamConfig config = new CmoMfiParamConfig();

  @Test
  public void getChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<?> specs = config.getChromosomeSpecs();

    assertThat(specs).hasSize(2);
  }

  @Test
  public void initialChromosomes_returnsExpectedChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    assertThat(chromosomes).hasSize(2);
    assertThat(chromosomes.get(0)).isInstanceOf(IntegerChromosome.class);
    assertThat(chromosomes.get(1)).isInstanceOf(IntegerChromosome.class);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsValidParameters()
      throws InvalidProtocolBufferException {
    // Create test chromosomes - IntegerChromosome.of(min, max, length) where length is the number
    // of genes
    IntegerChromosome cmoPeriodChromosome = IntegerChromosome.of(10, 30, 1);
    IntegerChromosome mfiPeriodChromosome = IntegerChromosome.of(10, 30, 1);

    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(cmoPeriodChromosome, mfiPeriodChromosome);

    Any parameters = config.createParameters(chromosomes);

    assertThat(parameters.is(CmoMfiParameters.class)).isTrue();

    CmoMfiParameters unpacked = parameters.unpack(CmoMfiParameters.class);
    assertThat(unpacked.getCmoPeriod()).isAtLeast(10);
    assertThat(unpacked.getCmoPeriod()).isAtMost(30);
    assertThat(unpacked.getMfiPeriod()).isAtLeast(10);
    assertThat(unpacked.getMfiPeriod()).isAtMost(30);
  }

  @Test
  public void createParameters_withInvalidChromosomes_returnsDefaultParameters()
      throws InvalidProtocolBufferException {
    ImmutableList<NumericChromosome<?, ?>> chromosomes = ImmutableList.of();

    Any parameters = config.createParameters(chromosomes);

    assertThat(parameters.is(CmoMfiParameters.class)).isTrue();

    CmoMfiParameters unpacked = parameters.unpack(CmoMfiParameters.class);
    assertThat(unpacked.getCmoPeriod()).isEqualTo(14);
    assertThat(unpacked.getMfiPeriod()).isEqualTo(14);
  }
}
