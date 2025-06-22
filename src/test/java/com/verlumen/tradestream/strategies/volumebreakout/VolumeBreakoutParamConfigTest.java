package com.verlumen.tradestream.strategies.volumebreakout;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.VolumeBreakoutParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class VolumeBreakoutParamConfigTest {

  private final VolumeBreakoutParamConfig config = new VolumeBreakoutParamConfig();

  @Test
  public void getChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<?> specs = config.getChromosomeSpecs();

    assertThat(specs).hasSize(1);
  }

  @Test
  public void initialChromosomes_returnsExpectedChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    assertThat(chromosomes).hasSize(1);
    assertThat(chromosomes.get(0)).isInstanceOf(DoubleChromosome.class);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsCorrectParameters()
      throws InvalidProtocolBufferException {
    // Create test chromosome - DoubleChromosome.of(min, max, length) where length is the number of
    // genes
    DoubleChromosome volumeMultiplierChromosome = DoubleChromosome.of(1.5, 3.0, 1);

    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(volumeMultiplierChromosome);

    Any result = config.createParameters(chromosomes);

    assertThat(result.is(VolumeBreakoutParameters.class)).isTrue();
    VolumeBreakoutParameters parameters = result.unpack(VolumeBreakoutParameters.class);
    assertThat(parameters.getVolumeMultiplier()).isAtLeast(1.5);
    assertThat(parameters.getVolumeMultiplier()).isAtMost(3.0);
  }

  @Test
  public void createParameters_withInvalidChromosomeCount_returnsDefaultParameters()
      throws InvalidProtocolBufferException {
    // Create empty chromosome list
    ImmutableList<NumericChromosome<?, ?>> chromosomes = ImmutableList.of();

    Any result = config.createParameters(chromosomes);

    assertThat(result.is(VolumeBreakoutParameters.class)).isTrue();
    VolumeBreakoutParameters parameters = result.unpack(VolumeBreakoutParameters.class);
    assertThat(parameters.getVolumeMultiplier()).isEqualTo(2.0);
  }
}
