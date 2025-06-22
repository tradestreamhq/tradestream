package com.verlumen.tradestream.strategies.linearregressionchannels;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.LinearRegressionChannelsParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class LinearRegressionChannelsParamConfigTest {
  private final LinearRegressionChannelsParamConfig config =
      new LinearRegressionChannelsParamConfig();

  @Test
  public void getChromosomeSpecs_returnsExpectedSpecs() {
    assertThat(config.getChromosomeSpecs()).hasSize(2);
  }

  @Test
  public void initialChromosomes_matchesSpecsSize() {
    assertThat(config.initialChromosomes()).hasSize(config.getChromosomeSpecs().size());
  }

  @Test
  public void createParameters_withDefaultChromosomes_returnsValidAny() throws Exception {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    Any packed = config.createParameters(chromosomes);
    assertThat(packed.is(LinearRegressionChannelsParameters.class)).isTrue();
    LinearRegressionChannelsParameters params =
        packed.unpack(LinearRegressionChannelsParameters.class);
    assertThat(params.getPeriod()).isGreaterThan(0);
    assertThat(params.getMultiplier()).isGreaterThan(0.0);
  }

  @Test
  public void createParameters_withCustomValues_returnsCorrectParameters() throws Exception {
    IntegerChromosome periodChrom = IntegerChromosome.of(10, 50);
    DoubleChromosome multiplierChrom = DoubleChromosome.of(1.0, 3.0);

    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(periodChrom, multiplierChrom);
    Any packed = config.createParameters(chromosomes);

    LinearRegressionChannelsParameters params =
        packed.unpack(LinearRegressionChannelsParameters.class);

    // Extract the actual values from chromosomes
    int expectedPeriod = periodChrom.gene().allele();
    double expectedMultiplier = multiplierChrom.gene().allele();

    assertThat(params.getPeriod()).isEqualTo(expectedPeriod);
    assertThat(params.getMultiplier()).isEqualTo(expectedMultiplier);

    // Also verify values are within expected ranges
    assertThat(params.getPeriod()).isAtLeast(10);
    assertThat(params.getPeriod()).isAtMost(50);
    assertThat(params.getMultiplier()).isAtLeast(1.0);
    assertThat(params.getMultiplier()).isAtMost(3.0);
  }
}
