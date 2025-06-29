package com.verlumen.tradestream.strategies.adxdmi;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.AdxDmiParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;

public class AdxDmiParamConfigTest {
  private AdxDmiParamConfig config;

  @Before
  public void setUp() {
    config = new AdxDmiParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(2);
  }

  @Test
  public void testCreateParameters() {
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(10, 30, 14), // ADX Period
            IntegerChromosome.of(10, 30, 14) // DI Period
            );
    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(AdxDmiParameters.class)).isTrue();
  }

  @Test
  public void testCreateParameters_invalidChromosomeSize_throwsException() {
    List<NumericChromosome<?, ?>> chromosomes = List.of(IntegerChromosome.of(10, 30, 14));
    assertThrows(
        IllegalArgumentException.class,
        () -> config.createParameters(ImmutableList.copyOf(chromosomes)));
  }

  @Test
  public void testInitialChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(2);
  }
}
