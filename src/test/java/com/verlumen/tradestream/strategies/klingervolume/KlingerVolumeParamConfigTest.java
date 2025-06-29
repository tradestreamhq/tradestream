package com.verlumen.tradestream.strategies.klingervolume;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.KlingerVolumeParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class KlingerVolumeParamConfigTest {

  private final KlingerVolumeParamConfig config = new KlingerVolumeParamConfig();

  @Test
  public void getChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<?> specs = config.getChromosomeSpecs();

    assertThat(specs).hasSize(3);
  }

  @Test
  public void initialChromosomes_returnsExpectedChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    assertThat(chromosomes).hasSize(3);
    assertThat(chromosomes.get(0)).isInstanceOf(IntegerChromosome.class);
    assertThat(chromosomes.get(1)).isInstanceOf(IntegerChromosome.class);
    assertThat(chromosomes.get(2)).isInstanceOf(IntegerChromosome.class);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsCorrectParameters()
      throws InvalidProtocolBufferException {
    // Create test chromosomes
    IntegerChromosome shortPeriodChromosome = IntegerChromosome.of(5, 15, 10);
    IntegerChromosome longPeriodChromosome = IntegerChromosome.of(20, 50, 35);
    IntegerChromosome signalPeriodChromosome = IntegerChromosome.of(5, 15, 10);

    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(shortPeriodChromosome, longPeriodChromosome, signalPeriodChromosome);

    Any result = config.createParameters(chromosomes);

    assertThat(result.is(KlingerVolumeParameters.class)).isTrue();
    KlingerVolumeParameters parameters = result.unpack(KlingerVolumeParameters.class);
    assertThat(parameters.getShortPeriod()).isAtLeast(5);
    assertThat(parameters.getShortPeriod()).isAtMost(15);
    assertThat(parameters.getLongPeriod()).isAtLeast(20);
    assertThat(parameters.getLongPeriod()).isAtMost(50);
    assertThat(parameters.getSignalPeriod()).isAtLeast(5);
    assertThat(parameters.getSignalPeriod()).isAtMost(15);
  }

  @Test
  public void createParameters_withInvalidChromosomeCount_returnsDefaultParameters()
      throws InvalidProtocolBufferException {
    // Create only 2 chromosomes instead of 3
    IntegerChromosome shortPeriodChromosome = IntegerChromosome.of(5, 15, 10);
    IntegerChromosome longPeriodChromosome = IntegerChromosome.of(20, 50, 35);

    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(shortPeriodChromosome, longPeriodChromosome);

    Any result = config.createParameters(chromosomes);

    assertThat(result.is(KlingerVolumeParameters.class)).isTrue();
    KlingerVolumeParameters parameters = result.unpack(KlingerVolumeParameters.class);
    assertThat(parameters.getShortPeriod()).isEqualTo(10);
    assertThat(parameters.getLongPeriod()).isEqualTo(35);
    assertThat(parameters.getSignalPeriod()).isEqualTo(10);
  }
}
