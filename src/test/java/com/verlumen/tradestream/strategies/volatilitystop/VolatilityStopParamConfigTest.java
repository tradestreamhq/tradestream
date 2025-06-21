package com.verlumen.tradestream.strategies.volatilitystop;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.VolatilityStopParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class VolatilityStopParamConfigTest {
  private VolatilityStopParamConfig config;

  @Before
  public void setUp() {
    config = new VolatilityStopParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(2);
  }

  @Test
  public void testCreateParameters_validChromosomes_returnsPackedParameters() {
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(5, 30, 14), // ATR Period
            DoubleChromosome.of(1.0, 5.0) // Multiplier
            );

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(VolatilityStopParameters.class)).isTrue();
  }

  @Test
  public void testGetStrategyType_returnsExpectedType() {
    assertThat(config.getStrategyType()).isEqualTo(StrategyType.VOLATILITY_STOP);
  }
}
