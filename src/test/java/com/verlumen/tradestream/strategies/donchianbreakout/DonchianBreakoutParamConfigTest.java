package com.verlumen.tradestream.strategies.donchianbreakout;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.DonchianBreakoutParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class DonchianBreakoutParamConfigTest {
  private DonchianBreakoutParamConfig config;

  @Before
  public void setUp() {
    config = new DonchianBreakoutParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(1);
  }

  @Test
  public void testCreateParameters_validChromosomes_returnsPackedParameters() {
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(IntegerChromosome.of(10, 50, 20)); // Donchian Period

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(DonchianBreakoutParameters.class)).isTrue();
  }
}
