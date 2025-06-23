package com.verlumen.tradestream.strategies.rocma;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.RocMaCrossoverParameters;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class RocMaCrossoverParamConfigTest {
  private final RocMaCrossoverParamConfig config = new RocMaCrossoverParamConfig();

  @Test
  public void testChromosomeSpecs() {
    assertThat(config.getChromosomeSpecs()).hasSize(2);
  }

  @Test
  public void testInitialChromosomes() {
    assertThat(config.initialChromosomes()).hasSize(2);
  }

  @Test
  public void testCreateParametersWithValidChromosomes() throws InvalidProtocolBufferException {
    NumericChromosome<?, ?> rocChromosome = config.getChromosomeSpecs().get(0).createChromosome();
    NumericChromosome<?, ?> maChromosome = config.getChromosomeSpecs().get(1).createChromosome();

    Any packed = config.createParameters(ImmutableList.of(rocChromosome, maChromosome));
    RocMaCrossoverParameters params = packed.unpack(RocMaCrossoverParameters.class);

    // The values will be within [5, 50], so just check the range
    assertThat(params.getRocPeriod()).isAtLeast(5);
    assertThat(params.getRocPeriod()).isAtMost(50);
    assertThat(params.getMaPeriod()).isAtLeast(5);
    assertThat(params.getMaPeriod()).isAtMost(50);
  }

  @Test
  public void testCreateParametersWithEmptyList() throws InvalidProtocolBufferException {
    Any packed = config.createParameters(ImmutableList.of());
    RocMaCrossoverParameters params = packed.unpack(RocMaCrossoverParameters.class);
    assertThat(params.getRocPeriod()).isEqualTo(10);
    assertThat(params.getMaPeriod()).isEqualTo(20);
  }

  @Test
  public void testCreateParametersWithWrongNumberOfChromosomes()
      throws InvalidProtocolBufferException {
    NumericChromosome<?, ?> chromosome = config.getChromosomeSpecs().get(0).createChromosome();
    Any packed = config.createParameters(ImmutableList.of(chromosome));
    RocMaCrossoverParameters params = packed.unpack(RocMaCrossoverParameters.class);
    assertThat(params.getRocPeriod()).isEqualTo(10);
    assertThat(params.getMaPeriod()).isEqualTo(20);
  }
}
