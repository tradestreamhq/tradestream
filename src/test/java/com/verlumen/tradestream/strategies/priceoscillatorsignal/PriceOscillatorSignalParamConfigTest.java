package com.verlumen.tradestream.strategies.priceoscillatorsignal;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.PriceOscillatorSignalParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class PriceOscillatorSignalParamConfigTest {

  private final PriceOscillatorSignalParamConfig config = new PriceOscillatorSignalParamConfig();

  @Test
  public void getChromosomeSpecs_returnsCorrectSpecs() {
    ImmutableList<?> specs = config.getChromosomeSpecs();

    assertThat(specs).hasSize(3);
  }

  @Test
  public void initialChromosomes_returnsCorrectNumberOfChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();

    assertThat(chromosomes).hasSize(3);
    assertThat(chromosomes.get(0)).isInstanceOf(IntegerChromosome.class);
    assertThat(chromosomes.get(1)).isInstanceOf(IntegerChromosome.class);
    assertThat(chromosomes.get(2)).isInstanceOf(IntegerChromosome.class);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsValidParameters()
      throws InvalidProtocolBufferException {
    // Create test chromosomes
    IntegerChromosome fastPeriodChromosome = IntegerChromosome.of(5, 20);
    IntegerChromosome slowPeriodChromosome = IntegerChromosome.of(10, 50);
    IntegerChromosome signalPeriodChromosome = IntegerChromosome.of(5, 20);

    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(fastPeriodChromosome, slowPeriodChromosome, signalPeriodChromosome);

    Any parametersAny = config.createParameters(chromosomes);

    assertThat(parametersAny.is(PriceOscillatorSignalParameters.class)).isTrue();

    PriceOscillatorSignalParameters parameters =
        parametersAny.unpack(PriceOscillatorSignalParameters.class);

    assertThat(parameters.getFastPeriod()).isEqualTo(fastPeriodChromosome.intValue());
    assertThat(parameters.getSlowPeriod()).isEqualTo(slowPeriodChromosome.intValue());
    assertThat(parameters.getSignalPeriod()).isEqualTo(signalPeriodChromosome.intValue());
  }

  @Test
  public void createParameters_withWrongNumberOfChromosomes_returnsDefaultParameters()
      throws InvalidProtocolBufferException {
    // Create only 2 chromosomes instead of 3
    IntegerChromosome fastPeriodChromosome = IntegerChromosome.of(5, 20);
    IntegerChromosome slowPeriodChromosome = IntegerChromosome.of(10, 50);

    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(fastPeriodChromosome, slowPeriodChromosome);

    Any parametersAny = config.createParameters(chromosomes);

    assertThat(parametersAny.is(PriceOscillatorSignalParameters.class)).isTrue();

    PriceOscillatorSignalParameters parameters =
        parametersAny.unpack(PriceOscillatorSignalParameters.class);

    // Should return default values
    assertThat(parameters.getFastPeriod()).isEqualTo(10);
    assertThat(parameters.getSlowPeriod()).isEqualTo(20);
    assertThat(parameters.getSignalPeriod()).isEqualTo(9);
  }
}
