package com.verlumen.tradestream.strategies.sarmfi;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.SarMfiParameters;
import io.jenetics.NumericChromosome;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import com.google.common.collect.ImmutableList;
import org.junit.Test;

public final class SarMfiParamConfigTest {
  private final ParamConfig config = new SarMfiParamConfig();

  @Test
  public void testGetChromosomeSpecs() {
    assertThat(config.getChromosomeSpecs().size()).isEqualTo(4);
  }

  @Test
  public void testInitialChromosomes() {
    assertThat(config.initialChromosomes().size()).isEqualTo(4);
  }

  @Test
  public void testCreateParameters_valid() throws Exception {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = ImmutableList.copyOf(config.initialChromosomes());
    Any packed = config.createParameters(chromosomes);
    SarMfiParameters params = packed.unpack(SarMfiParameters.class);
    assertThat(params.hasAccelerationFactorStart()).isTrue();
    assertThat(params.hasAccelerationFactorIncrement()).isTrue();
    assertThat(params.hasAccelerationFactorMax()).isTrue();
    assertThat(params.hasMfiPeriod()).isTrue();
  }

  @Test
  public void testCreateParameters_empty() throws Exception {
    Any packed = config.createParameters(ImmutableList.of());
    SarMfiParameters params = packed.unpack(SarMfiParameters.class);
    assertThat(params.hasAccelerationFactorStart()).isTrue();
    assertThat(params.hasAccelerationFactorIncrement()).isTrue();
    assertThat(params.hasAccelerationFactorMax()).isTrue();
    assertThat(params.hasMfiPeriod()).isTrue();
  }
} 