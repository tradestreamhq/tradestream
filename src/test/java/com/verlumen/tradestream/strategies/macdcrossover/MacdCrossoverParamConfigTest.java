package com.verlumen.tradestream.strategies.macdcrossover;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.MacdCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class MacdCrossoverParamConfigTest {
  private MacdCrossoverParamConfig config;

  @Before
  public void setUp() {
    config = new MacdCrossoverParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(3);
  }

  @Test
  public void testCreateParameters_validChromosomes_returnsPackedParameters() {
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(5, 20, 12),  // Short EMA Period
            IntegerChromosome.of(15, 50, 26), // Long EMA Period
            IntegerChromosome.of(5, 20, 9)    // Signal Period
        );

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(MacdCrossoverParameters.class)).isTrue();
  }

  @Test
  public void testGetStrategyType_returnsExpectedType() {
    assertThat(config.getStrategyType()).isEqualTo(StrategyType.MACD_CROSSOVER);
  }
}
