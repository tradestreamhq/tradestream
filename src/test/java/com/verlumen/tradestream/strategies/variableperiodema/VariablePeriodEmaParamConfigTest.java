package com.verlumen.tradestream.strategies.variableperiodema;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ParamConfig;
import com.verlumen.tradestream.strategies.VariablePeriodEmaParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public final class VariablePeriodEmaParamConfigTest {
  private ParamConfig paramConfig;

  @Before
  public void setUp() {
    paramConfig = new VariablePeriodEmaParamConfig();
  }

  @Test
  public void getChromosomeSpecs_size() {
    assertThat(paramConfig.getChromosomeSpecs().size()).isEqualTo(2);
  }

  @Test
  public void initialChromosomes_size() {
    assertThat(paramConfig.initialChromosomes().size()).isEqualTo(2);
  }

  @Test
  public void createParameters_validInput() throws Exception {
    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(IntegerChromosome.of(5, 50, 15), IntegerChromosome.of(10, 100, 40));
    Any packed = paramConfig.createParameters(chromosomes);
    assertThat(packed.is(VariablePeriodEmaParameters.class)).isTrue();
  }

  @Test(expected = IllegalArgumentException.class)
  public void createParameters_invalidInput_throws() {
    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(IntegerChromosome.of(5, 50, 15));
    paramConfig.createParameters(chromosomes);
  }
}
