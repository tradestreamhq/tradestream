package com.verlumen.tradestream.strategies.gannswing;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.GannSwingParameters;
import io.jenetics.NumericChromosome;
import com.google.common.collect.ImmutableList;
import org.junit.Test;

public final class GannSwingParamConfigTest {
  private final ParamConfig config = new GannSwingParamConfig();

  @Test
  public void testGetChromosomeSpecs() {
    assertThat(config.getChromosomeSpecs().size()).isEqualTo(1);
  }

  @Test
  public void testInitialChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = ImmutableList.copyOf(config.initialChromosomes());
    assertThat(chromosomes).isNotNull();
    assertThat(chromosomes.size()).isEqualTo(1);
  }

  @Test
  public void testCreateParameters_valid() throws Exception {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = ImmutableList.copyOf(config.initialChromosomes());
    Any packed = config.createParameters(chromosomes);
    GannSwingParameters params = packed.unpack(GannSwingParameters.class);
    assertThat(params.hasGannPeriod()).isTrue();
  }

  @Test
  public void testCreateParameters_empty() throws Exception {
    Any packed = config.createParameters(ImmutableList.of());
    GannSwingParameters params = packed.unpack(GannSwingParameters.class);
    assertThat(params.hasGannPeriod()).isTrue();
  }
} 