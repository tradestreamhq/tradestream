package com.verlumen.tradestream.strategies.massindex;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.MassIndexParameters;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class MassIndexParamConfigTest {
  private final MassIndexParamConfig config = new MassIndexParamConfig();

  @Test
  public void getChromosomeSpecs_returnsExpectedSpecs() {
    assertThat(config.getChromosomeSpecs()).hasSize(2);
  }

  @Test
  public void initialChromosomes_matchesSpecsSize() {
    assertThat(config.initialChromosomes()).hasSize(config.getChromosomeSpecs().size());
  }

  @Test
  public void createParameters_withDefaultChromosomes_returnsValidAny() throws Exception {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    Any packed = config.createParameters(chromosomes);
    assertThat(packed.is(MassIndexParameters.class)).isTrue();
    MassIndexParameters params = packed.unpack(MassIndexParameters.class);
    assertThat(params.getEmaPeriod()).isGreaterThan(0);
    assertThat(params.getSumPeriod()).isGreaterThan(0);
  }
} 