package com.verlumen.tradestream.strategies.rsiemacrossover;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.RsiEmaCrossoverParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class RsiEmaCrossoverParamConfigTest {
  private RsiEmaCrossoverParamConfig config;

  @Before
  public void setUp() {
    config = new RsiEmaCrossoverParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(2);

    // RSI Period (5-30)
    assertThat(specs.get(0).getRange().lowerEndpoint()).isEqualTo(5);
    assertThat(specs.get(0).getRange().upperEndpoint()).isEqualTo(30);

    // EMA Period (5-20)
    assertThat(specs.get(1).getRange().lowerEndpoint()).isEqualTo(5);
    assertThat(specs.get(1).getRange().upperEndpoint()).isEqualTo(20);
  }

  @Test
  public void testCreateParameters_validChromosomes_returnsPackedParameters() {
    // Create chromosomes with correct parameter order: min, max, value
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(5, 30, 14), // RSI Period
            IntegerChromosome.of(5, 20, 10) // EMA Period
            );

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(RsiEmaCrossoverParameters.class)).isTrue();
  }

  @Test
  public void testCreateParameters_invalidChromosomeSize_throwsException() {
    // Create a single chromosome with correct parameter order: min, max, value
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(IntegerChromosome.of(5, 30, 14)); // Only one chromosome

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class,
            () -> config.createParameters(ImmutableList.copyOf(chromosomes)));
    assertThat(thrown).hasMessageThat().contains("Expected 2 chromosomes but got 1");
  }

  @Test
  public void testInitialChromosomes_returnsExpectedSize() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(2);

    // Verify they are all IntegerChromosomes
    assertThat(chromosomes.get(0)).isInstanceOf(IntegerChromosome.class);
    assertThat(chromosomes.get(1)).isInstanceOf(IntegerChromosome.class);

    // Verify ranges
    IntegerChromosome rsiPeriod = (IntegerChromosome) chromosomes.get(0);
    assertThat(rsiPeriod.gene().min()).isEqualTo(5);
    assertThat(rsiPeriod.gene().max()).isEqualTo(30);

    IntegerChromosome emaPeriod = (IntegerChromosome) chromosomes.get(1);
    assertThat(emaPeriod.gene().min()).isEqualTo(5);
    assertThat(emaPeriod.gene().max()).isEqualTo(20);
  }
}
