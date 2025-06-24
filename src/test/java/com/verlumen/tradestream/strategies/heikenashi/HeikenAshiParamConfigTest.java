package com.verlumen.tradestream.strategies.heikenashi;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.HeikenAshiParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class HeikenAshiParamConfigTest {
  private HeikenAshiParamConfig config;

  @Before
  public void setUp() {
    config = new HeikenAshiParamConfig();
  }

  @Test
  public void testSpecs_returnsExpectedSize() {
    assertThat(config.getChromosomeSpecs()).hasSize(1);
  }

  @Test
  public void testInitialChromosomes_returnsExpectedSize() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(1);
    assertThat(chromosomes.get(0)).isInstanceOf(IntegerChromosome.class);
    IntegerChromosome period = (IntegerChromosome) chromosomes.get(0);
    assertThat(period.min()).isEqualTo(2);
    assertThat(period.max()).isEqualTo(30);
  }

  @Test
  public void testToParameters_packsCorrectly() throws Exception {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    Any packed = config.createParameters(chromosomes);
    HeikenAshiParameters params = packed.unpack(HeikenAshiParameters.class);
    assertThat(params.getPeriod()).isAtLeast(2);
    assertThat(params.getPeriod()).isAtMost(30);
  }
}
