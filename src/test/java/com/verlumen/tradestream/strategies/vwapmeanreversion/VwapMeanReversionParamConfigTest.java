package com.verlumen.tradestream.strategies.vwapmeanreversion;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.strategies.VwapMeanReversionParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import org.junit.Test;

public final class VwapMeanReversionParamConfigTest {

  private final VwapMeanReversionParamConfig config = new VwapMeanReversionParamConfig();

  @Test
  public void getChromosomeSpecs_returnsCorrectSize() {
    assertThat(config.getChromosomeSpecs()).hasSize(3);
  }

  @Test
  public void initialChromosomes_returnsCorrectSize() {
    assertThat(config.initialChromosomes()).hasSize(3);
  }

  @Test
  public void createParameters_withValidChromosomes_returnsValidParameters() throws Exception {
    // Create test chromosomes
    IntegerChromosome vwapPeriodChromosome = IntegerChromosome.of(10, 50);
    IntegerChromosome movingAveragePeriodChromosome = IntegerChromosome.of(10, 50);
    DoubleChromosome deviationMultiplierChromosome = DoubleChromosome.of(1.0, 3.0);

    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(
            vwapPeriodChromosome, movingAveragePeriodChromosome, deviationMultiplierChromosome);

    Any result = config.createParameters(chromosomes);

    VwapMeanReversionParameters parameters = result.unpack(VwapMeanReversionParameters.class);
    assertThat(parameters.getVwapPeriod()).isEqualTo(vwapPeriodChromosome.gene().intValue());
    assertThat(parameters.getMovingAveragePeriod())
        .isEqualTo(movingAveragePeriodChromosome.gene().intValue());
    assertThat(parameters.getDeviationMultiplier())
        .isEqualTo(deviationMultiplierChromosome.gene().doubleValue());
  }

  @Test
  public void createParameters_withInsufficientChromosomes_returnsDefaultParameters()
      throws Exception {
    // Create only 2 chromosomes instead of 3
    IntegerChromosome vwapPeriodChromosome = IntegerChromosome.of(10, 50);
    IntegerChromosome movingAveragePeriodChromosome = IntegerChromosome.of(10, 50);

    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(vwapPeriodChromosome, movingAveragePeriodChromosome);

    Any result = config.createParameters(chromosomes);

    VwapMeanReversionParameters parameters = result.unpack(VwapMeanReversionParameters.class);
    assertThat(parameters.getVwapPeriod()).isEqualTo(20);
    assertThat(parameters.getMovingAveragePeriod()).isEqualTo(20);
    assertThat(parameters.getDeviationMultiplier()).isEqualTo(2.0);
  }

  @Test
  public void createParameters_withExcessiveChromosomes_returnsDefaultParameters()
      throws Exception {
    // Create 4 chromosomes instead of 3
    IntegerChromosome vwapPeriodChromosome = IntegerChromosome.of(10, 50);
    IntegerChromosome movingAveragePeriodChromosome = IntegerChromosome.of(10, 50);
    DoubleChromosome deviationMultiplierChromosome = DoubleChromosome.of(1.0, 3.0);
    IntegerChromosome extraChromosome = IntegerChromosome.of(1, 10);

    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(
            vwapPeriodChromosome,
            movingAveragePeriodChromosome,
            deviationMultiplierChromosome,
            extraChromosome);

    Any result = config.createParameters(chromosomes);

    VwapMeanReversionParameters parameters = result.unpack(VwapMeanReversionParameters.class);
    assertThat(parameters.getVwapPeriod()).isEqualTo(20);
    assertThat(parameters.getMovingAveragePeriod()).isEqualTo(20);
    assertThat(parameters.getDeviationMultiplier()).isEqualTo(2.0);
  }

  @Test
  public void createParameters_withMixedChromosomeTypes_returnsValidParameters() throws Exception {
    // Test with mixed chromosome types
    DoubleChromosome vwapPeriodChromosome = DoubleChromosome.of(10.0, 50.0);
    DoubleChromosome movingAveragePeriodChromosome = DoubleChromosome.of(10.0, 50.0);
    DoubleChromosome deviationMultiplierChromosome = DoubleChromosome.of(1.0, 3.0);

    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(
            vwapPeriodChromosome, movingAveragePeriodChromosome, deviationMultiplierChromosome);

    Any result = config.createParameters(chromosomes);

    VwapMeanReversionParameters parameters = result.unpack(VwapMeanReversionParameters.class);
    assertThat(parameters.getVwapPeriod())
        .isEqualTo((int) vwapPeriodChromosome.gene().doubleValue());
    assertThat(parameters.getMovingAveragePeriod())
        .isEqualTo((int) movingAveragePeriodChromosome.gene().doubleValue());
    assertThat(parameters.getDeviationMultiplier())
        .isEqualTo(deviationMultiplierChromosome.gene().doubleValue());
  }
}
