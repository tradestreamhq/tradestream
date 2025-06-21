package com.verlumen.tradestream.strategies.stochasticsrsi;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.StochasticRsiParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class StochasticRsiParamConfigTest {
  private StochasticRsiParamConfig config;

  @Before
  public void setUp() {
    config = new StochasticRsiParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(5);
  }

  @Test
  public void testCreateParameters_validChromosomes_returnsPackedParameters() {
    // Create chromosomes with correct parameter order: min, max, value
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(5, 30, 14), // RSI Period
            IntegerChromosome.of(5, 30, 14), // Stochastic K Period
            IntegerChromosome.of(3, 15, 3), // Stochastic D Period
            IntegerChromosome.of(60, 95, 80), // Overbought Threshold
            IntegerChromosome.of(5, 40, 20) // Oversold Threshold
            );

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(StochasticRsiParameters.class)).isTrue();
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
    assertThat(thrown).hasMessageThat().contains("Expected 5 chromosomes but got 1");
  }

  @Test
  public void testInitialChromosomes_returnsExpectedSize() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(5);
  }

  @Test
  public void testGetStrategyType_returnsExpectedType() {
    assertThat(config.getStrategyType()).isEqualTo(StrategyType.STOCHASTIC_RSI);
  }
}
