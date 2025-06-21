package com.verlumen.tradestream.strategies.tripleemacrossover;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.TripleEmaCrossoverParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class TripleEmaCrossoverParamConfigTest {
  private TripleEmaCrossoverParamConfig config;

  @Before
  public void setUp() {
    config = new TripleEmaCrossoverParamConfig();
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
            IntegerChromosome.of(2, 20, 10), // Short EMA Period
            IntegerChromosome.of(10, 50, 20), // Medium EMA Period
            IntegerChromosome.of(20, 100, 50) // Long EMA Period
            );

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(TripleEmaCrossoverParameters.class)).isTrue();
  }
}
