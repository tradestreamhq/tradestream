package com.verlumen.tradestream.strategies.frama;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.FramaParameters;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class FramaParamConfigTest {
  private final FramaParamConfig config = new FramaParamConfig();

  @Test
  public void testChromosomeSpecs() {
    assertThat(config.getChromosomeSpecs()).hasSize(3);
  }

  @Test
  public void testInitialChromosomes() {
    assertThat(config.initialChromosomes()).hasSize(3);
  }

  @Test
  public void testCreateParameters_valid() throws InvalidProtocolBufferException {
    NumericChromosome<?, ?> scChrom = config.getChromosomeSpecs().get(0).createChromosome();
    NumericChromosome<?, ?> fcChrom = config.getChromosomeSpecs().get(1).createChromosome();
    NumericChromosome<?, ?> alphaChrom = config.getChromosomeSpecs().get(2).createChromosome();
    Any packed = config.createParameters(ImmutableList.of(scChrom, fcChrom, alphaChrom));
    FramaParameters params = packed.unpack(FramaParameters.class);
    assertThat(params.getSc()).isAtLeast(0.1);
    assertThat(params.getSc()).isAtMost(2.0);
    assertThat(params.getFc()).isAtLeast(5);
    assertThat(params.getFc()).isAtMost(50);
    assertThat(params.getAlpha()).isAtLeast(0.1);
    assertThat(params.getAlpha()).isAtMost(1.0);
  }

  @Test
  public void testCreateParameters_invalid() throws InvalidProtocolBufferException {
    Any packed = config.createParameters(ImmutableList.of());
    FramaParameters params = packed.unpack(FramaParameters.class);
    assertThat(params.getSc()).isEqualTo(0.5);
    assertThat(params.getFc()).isEqualTo(20);
    assertThat(params.getAlpha()).isEqualTo(0.5);
  }
}
