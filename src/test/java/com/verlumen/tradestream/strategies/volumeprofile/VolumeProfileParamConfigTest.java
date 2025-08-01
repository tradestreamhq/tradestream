package com.verlumen.tradestream.strategies.volumeprofile;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.VolumeProfileParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.IntegerGene;
import org.junit.Test;

public final class VolumeProfileParamConfigTest {

  private final VolumeProfileParamConfig config = new VolumeProfileParamConfig();

  @Test
  public void getChromosomeSpecs_returnsExpectedSpecs() {
    assertThat(config.getChromosomeSpecs()).hasSize(1);
  }

  @Test
  public void initialChromosomes_returnsExpectedChromosomes() {
    assertThat(config.initialChromosomes()).hasSize(1);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsValidParameters()
      throws InvalidProtocolBufferException {
    ImmutableList<IntegerChromosome> chromosomes =
        ImmutableList.of(IntegerChromosome.of(IntegerGene.of(50, 10, 100)));

    Any parameters = config.createParameters(chromosomes);
    VolumeProfileParameters unpacked = parameters.unpack(VolumeProfileParameters.class);

    assertThat(unpacked.getPeriod()).isEqualTo(50);
  }

  @Test
  public void createParameters_withInvalidChromosomes_returnsDefaultParameters()
      throws InvalidProtocolBufferException {
    ImmutableList<IntegerChromosome> chromosomes = ImmutableList.of();

    Any parameters = config.createParameters(chromosomes);
    VolumeProfileParameters unpacked = parameters.unpack(VolumeProfileParameters.class);

    assertThat(unpacked.getPeriod()).isEqualTo(20);
  }
}
