package com.verlumen.tradestream.backtesting.oscillators;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.backtesting.ChromosomeSpec;
import com.verlumen.tradestream.strategies.AdxStochasticParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.IntegerGene;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(MockitoJUnitRunner.class)
public class AdxStochasticParamConfigTest {
  private AdxStochasticParamConfig config;

  @Before
  public void setUp() {
    config = AdxStochasticParamConfig.create();
  }

  @Test
  public void testGetChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(5);
  }

  @Test
  public void testCreateParameters_validChromosomes_returnsPackedParameters() {
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(15, 10, 30),
            IntegerChromosome.of(10, 5, 20),
            IntegerChromosome.of(5, 3, 15),
            IntegerChromosome.of(70, 60, 90),
            IntegerChromosome.of(20, 10, 40));

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(AdxStochasticParameters.class)).isTrue();
  }

  @Test
  public void testCreateParameters_invalidChromosomeSize_throwsException() {
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(IntegerChromosome.of(15, 10, 30)); // Only one chromosome

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class, () -> config.createParameters(ImmutableList.copyOf(chromosomes)));
    assertThat(thrown).hasMessageThat().contains("Expected 5 chromosomes but got 1");
  }

  @Test
  public void testInitialChromosomes_returnsExpectedSize() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(5);
  }

  @Test
  public void testGetStrategyType_returnsExpectedType() {
    assertThat(config.getStrategyType()).isEqualTo(StrategyType.ADX_STOCHASTIC);
  }
}
