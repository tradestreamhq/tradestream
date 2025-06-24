package com.verlumen.tradestream.strategies.elderrayma;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.ElderRayMAParameters;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class ElderRayMAParamConfigTest {
  private final ElderRayMAParamConfig config = new ElderRayMAParamConfig();

  @Test
  public void testChromosomeSpecs() {
    assertThat(config.getChromosomeSpecs()).hasSize(1);
  }

  @Test
  public void testInitialChromosomes() {
    assertThat(config.initialChromosomes()).hasSize(1);
  }

  @Test
  public void testCreateParameters_valid() throws Exception {
    NumericChromosome<?, ?> chromosome = config.getChromosomeSpecs().get(0).createChromosome();
    Any packed = config.createParameters(ImmutableList.of(chromosome));
    ElderRayMAParameters params = packed.unpack(ElderRayMAParameters.class);
    assertThat(params.getEmaPeriod()).isAtLeast(5);
    assertThat(params.getEmaPeriod()).isAtMost(50);
  }

  @Test
  public void testCreateParameters_invalid() throws Exception {
    // Should fallback to default if wrong chromosome count
    Any packed = config.createParameters(ImmutableList.of());
    ElderRayMAParameters params = packed.unpack(ElderRayMAParameters.class);
    assertThat(params.getEmaPeriod()).isEqualTo(20);
  }
}
