package com.verlumen.tradestream.strategies.stochasticema;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.StochasticEmaParameters;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class StochasticEmaParamConfigTest {
  private final StochasticEmaParamConfig config = new StochasticEmaParamConfig();

  @Test
  public void getChromosomeSpecs_returnsExpectedSpecs() {
    assertThat(config.getChromosomeSpecs()).hasSize(5);
  }

  @Test
  public void initialChromosomes_matchesSpecsSize() {
    assertThat(config.initialChromosomes()).hasSize(config.getChromosomeSpecs().size());
  }

  @Test
  public void createParameters_withDefaultChromosomes_returnsValidAny() throws Exception {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    Any packed = config.createParameters(chromosomes);
    assertThat(packed.is(StochasticEmaParameters.class)).isTrue();
    StochasticEmaParameters params = packed.unpack(StochasticEmaParameters.class);
    assertThat(params.getEmaPeriod()).isGreaterThan(0);
    assertThat(params.getStochasticKPeriod()).isGreaterThan(0);
    assertThat(params.getStochasticDPeriod()).isGreaterThan(0);
    assertThat(params.getOverboughtThreshold()).isGreaterThan(0);
    assertThat(params.getOversoldThreshold()).isGreaterThan(0);
  }
}
