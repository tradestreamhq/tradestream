package com.verlumen.tradestream.strategies.renkochart;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.RenkoChartParameters;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class RenkoChartParamConfigTest {
  private final ParamConfig config = new RenkoChartParamConfig();

  @Test
  public void testGetChromosomeSpecs() {
    assertThat(config.getChromosomeSpecs().size()).isEqualTo(1);
  }

  @Test
  public void testInitialChromosomes() {
    assertThat(config.initialChromosomes().size()).isEqualTo(1);
  }

  @Test
  public void testCreateParameters_valid() throws Exception {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes =
        ImmutableList.copyOf(config.initialChromosomes());
    Any packed = config.createParameters(chromosomes);
    RenkoChartParameters params = packed.unpack(RenkoChartParameters.class);
    assertThat(params.hasBrickSize()).isTrue();
  }

  @Test
  public void testCreateParameters_empty() throws Exception {
    Any packed = config.createParameters(ImmutableList.of());
    RenkoChartParameters params = packed.unpack(RenkoChartParameters.class);
    assertThat(params.hasBrickSize()).isTrue();
  }
}
