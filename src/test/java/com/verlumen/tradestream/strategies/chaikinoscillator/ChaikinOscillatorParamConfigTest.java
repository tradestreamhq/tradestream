package com.verlumen.tradestream.strategies.chaikinoscillator;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.ChaikinOscillatorParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;

public class ChaikinOscillatorParamConfigTest {
  private ChaikinOscillatorParamConfig config;

  @Before
  public void setUp() {
    config = new ChaikinOscillatorParamConfig();
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
            IntegerChromosome.of(2, 20, 3), // Fast Period
            IntegerChromosome.of(5, 50, 10) // Slow Period
            );
    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(ChaikinOscillatorParameters.class)).isTrue();
  }

  @Test
  public void testCreateParameters_invalidChromosomeSize_throwsException() {
    List<NumericChromosome<?, ?>> chromosomes = List.of(IntegerChromosome.of(2, 20, 3));
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
