package com.verlumen.tradestream.strategies.rangebars;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.RangeBarsParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import com.google.common.collect.ImmutableList;
import org.junit.Test;

public final class RangeBarsParamConfigTest {
  private final ParamConfig config = new RangeBarsParamConfig();

  @Test
  public void testGetChromosomeSpecs() {
    assertThat(config.getChromosomeSpecs().size()).isEqualTo(1);
  }

  @Test
  public void testInitialChromosomes() {
    List<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(1);
    assertThat(chromosomes.get(0)).isInstanceOf(DoubleChromosome.class);
  }

  @Test
  public void testCreateParameters_valid() throws Exception {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = ImmutableList.copyOf(config.initialChromosomes());
    Any packed = config.createParameters(chromosomes);
    RangeBarsParameters params = packed.unpack(RangeBarsParameters.class);
    assertThat(params.hasRangeSize()).isTrue();
  }

  @Test
  public void testCreateParameters_empty() throws Exception {
    Any packed = config.createParameters(ImmutableList.of());
    RangeBarsParameters params = packed.unpack(RangeBarsParameters.class);
    assertThat(params.hasRangeSize()).isTrue();
  }
} 