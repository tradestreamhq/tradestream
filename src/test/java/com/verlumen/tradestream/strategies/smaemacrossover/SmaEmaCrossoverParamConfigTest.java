package com.verlumen.tradestream.strategies.smaemacrossover;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.SmaEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class SmaEmaCrossoverParamConfigTest {
  private SmaEmaCrossoverParamConfig config;

  @Before
  public void setUp() {
    config = new SmaEmaCrossoverParamConfig();
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
            IntegerChromosome.of(5, 50, 20), // SMA Period
            IntegerChromosome.of(5, 50, 14) // EMA Period
            );

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(SmaEmaCrossoverParameters.class)).isTrue();
  }
}
