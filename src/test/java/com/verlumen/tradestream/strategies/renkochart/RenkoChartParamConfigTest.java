package com.verlumen.tradestream.strategies.renkochart;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Test;
import com.verlumen.tradestream.strategies.RenkoChartParameters;

public final class RenkoChartParamConfigTest {
  private final RenkoChartParamConfig config = new RenkoChartParamConfig();

  @Test
  public void testChromosomeSpecs() {
    assertThat(config.getChromosomeSpecs()).hasSize(1);
  }

  @Test
  public void testInitialChromosomes() {
    List<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(1);
  }

  @Test
  public void testCreateParameters_valid() throws Exception {
    List<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    Any packed = config.createParameters(ImmutableList.copyOf(chromosomes));
    RenkoChartParameters params = packed.unpack(RenkoChartParameters.class);
    assertThat(params.hasBrickSize()).isTrue();
    assertThat(params.getBrickSize()).isAtLeast(0.1);
    assertThat(params.getBrickSize()).isAtMost(100.0);
  }

  @Test
  public void testCreateParameters_empty() throws Exception {
    Any packed = config.createParameters(ImmutableList.of());
    RenkoChartParameters params = packed.unpack(RenkoChartParameters.class);
    assertThat(params.hasBrickSize()).isTrue();
    assertThat(params.getBrickSize()).isAtLeast(0.1);
  }
}
