package com.verlumen.tradestream.backtesting.params;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.Range;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import io.jenetics.Chromosome;
import io.jenetics.Genotype;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericGene;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

/** Unit tests for SmaRsiParamConfig. */
@RunWith(JUnit4.class)
public class SmaRsiParamConfigTest {
  private SmaRsiParamConfig config;

  @Before
  public void setUp() {
    config = new SmaRsiParamConfig();
  }

  @Test
  public void getChromosomes_returnsExpectedRanges() {
    // Act
    List<Range<Number>> ranges = config.getChromosomes();

    // Assert
    assertThat(ranges).hasSize(4); // 4 parameters: MA period, RSI period, Overbought, Oversold

    // Moving Average Period (5-50)
    assertThat(ranges.get(0).lowerEndpoint()).isEqualTo(5);
    assertThat(ranges.get(0).upperEndpoint()).isEqualTo(50);

    // RSI Period (2-30)
    assertThat(ranges.get(1).lowerEndpoint()).isEqualTo(2);
    assertThat(ranges.get(1).upperEndpoint()).isEqualTo(30);

    // Overbought Threshold (60.0-85.0)
    assertThat(ranges.get(2).lowerEndpoint()).isEqualTo(60.0);
    assertThat(ranges.get(2).upperEndpoint()).isEqualTo(85.0);

    // Oversold Threshold (15.0-40.0)
    assertThat(ranges.get(3).lowerEndpoint()).isEqualTo(15.0);
    assertThat(ranges.get(3).upperEndpoint()).isEqualTo(40.0);
  }

  @Test
  public void createParameters_convertsGenotypeCorrectly() throws Exception {
    // Arrange
    double movingAveragePeriod = 14.0;
    double rsiPeriod = 7.0;
    double overboughtThreshold = 70.0;
    double oversoldThreshold = 30.0;

    // Construct a Genotype matching ParamConfig’s shape:
    Genotype<NumericGene<? extends Number>> genotype =
        Genotype.of(
            IntegerChromosome.of(5, 50, (int) movingAveragePeriod),
            IntegerChromosome.of(2, 30, (int) rsiPeriod),
            DoubleChromosome.of(60.0, 85.0, overboughtThreshold),
            DoubleChromosome.of(15.0, 40.0, oversoldThreshold));

    // Act
    SmaRsiParameters params = config.createParameters(genotype).unpack(SmaRsiParameters.class);

    // Assert
    assertThat(params.getMovingAveragePeriod()).isEqualTo((int) movingAveragePeriod);
    assertThat(params.getRsiPeriod()).isEqualTo((int) rsiPeriod);
    assertThat(params.getOverboughtThreshold()).isEqualTo(overboughtThreshold);
    assertThat(params.getOversoldThreshold()).isEqualTo(oversoldThreshold);
  }

  @Test
  public void createParameters_roundsPeriodsToIntegers() throws Exception {
    // Arrange
    // We'll pass in values like 14.7 and 7.3; the Chromosome itself only stores int for these genes.
    double movingAveragePeriod = 14.7; // user-chosen, but effectively 14
    double rsiPeriod = 7.3;           // effectively 7
    double overboughtThreshold = 70.0;
    double oversoldThreshold = 30.0;

    Genotype<NumericGene<? extends Number>> genotype =
        Genotype.of(
            IntegerChromosome.of(5, 50, (int) movingAveragePeriod),
            IntegerChromosome.of(2, 30, (int) rsiPeriod),
            DoubleChromosome.of(60.0, 85.0, overboughtThreshold),
            DoubleChromosome.of(15.0, 40.0, oversoldThreshold));

    // Act
    SmaRsiParameters params = config.createParameters(genotype).unpack(SmaRsiParameters.class);

    // Because the gene is an IntegerGene, 14.7 -> 14, 7.3 -> 7
    assertThat(params.getMovingAveragePeriod()).isEqualTo(14);
    assertThat(params.getRsiPeriod()).isEqualTo(7);
  }

  @Test
  public void createParameters_preservesThresholdPrecision() throws Exception {
    // Arrange
    double overboughtThreshold = 70.5;
    double oversoldThreshold = 29.5;
    int maPeriod = 14;
    int rsiPeriod = 7;

    // For thresholds, we use DoubleChromosome to preserve decimals
    Genotype<NumericGene<? extends Number>> genotype =
        Genotype.of(
            IntegerChromosome.of(5, 50, maPeriod),
            IntegerChromosome.of(2, 30, rsiPeriod),
            DoubleChromosome.of(60.0, 85.0, overboughtThreshold),
            DoubleChromosome.of(15.0, 40.0, oversoldThreshold));

    // Act
    SmaRsiParameters params = config.createParameters(genotype).unpack(SmaRsiParameters.class);

    // Assert
    assertThat(params.getOverboughtThreshold()).isEqualTo(overboughtThreshold);
    assertThat(params.getOversoldThreshold()).isEqualTo(oversoldThreshold);
  }
}
