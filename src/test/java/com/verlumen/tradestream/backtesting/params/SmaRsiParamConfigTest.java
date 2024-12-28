package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.Range;
import com.google.inject.Guice;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.DoubleGene;
import io.jenetics.Genotype;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.MockitoAnnotations;

@RunWith(JUnit4.class)
public class SmaRsiParamConfigTest {
    private SmaRsiParamConfig config;

    @Before
    public void setUp() {
        MockitoAnnotations.openMocks(this);
        config = new SmaRsiParamConfig();
    }

    @Test
    public void getChromosomes_returnsExpectedRanges() {
        // Act
        List<Range<Integer>> ranges = config.getChromosomes();

        // Assert
        assertThat(ranges).hasSize(4); // MovingAverage, RSI, Overbought, Oversold

        // Moving Average Period (5-50)
        assertThat(ranges.get(0).min()).isEqualTo(5.0);
        assertThat(ranges.get(0).max()).isEqualTo(50.0);

        // RSI Period (2-30)
        assertThat(ranges.get(1).min()).isEqualTo(2.0);
        assertThat(ranges.get(1).max()).isEqualTo(30.0);

        // Overbought Threshold (60-85)
        assertThat(ranges.get(2).min()).isEqualTo(60.0);
        assertThat(ranges.get(2).max()).isEqualTo(85.0);

        // Oversold Threshold (15-40)
        assertThat(ranges.get(3).min()).isEqualTo(15.0);
        assertThat(ranges.get(3).max()).isEqualTo(40.0);
    }

    @Test
    public void createParameters_convertsGenotypeCorrectly() throws Exception {
        // Arrange
        double movingAveragePeriod = 14.0;
        double rsiPeriod = 7.0;
        double overboughtThreshold = 70.0;
        double oversoldThreshold = 30.0;

        Genotype<DoubleGene> genotype = Genotype.of(
            DoubleChromosome.of(DoubleGene.of(movingAveragePeriod, 5, 50)),
            DoubleChromosome.of(DoubleGene.of(rsiPeriod, 2, 30)),
            DoubleChromosome.of(DoubleGene.of(overboughtThreshold, 60, 85)),
            DoubleChromosome.of(DoubleGene.of(oversoldThreshold, 15, 40))
        );

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
        double movingAveragePeriod = 14.7;  // Should round to 14
        double rsiPeriod = 7.3;             // Should round to 7

        Genotype<DoubleGene> genotype = Genotype.of(
            DoubleChromosome.of(DoubleGene.of(movingAveragePeriod, 5, 50)),
            DoubleChromosome.of(DoubleGene.of(rsiPeriod, 2, 30)),
            DoubleChromosome.of(DoubleGene.of(70.0, 60, 85)),
            DoubleChromosome.of(DoubleGene.of(30.0, 15, 40))
        );

        // Act
        SmaRsiParameters params = config.createParameters(genotype).unpack(SmaRsiParameters.class);

        // Assert
        assertThat(params.getMovingAveragePeriod()).isEqualTo(14);
        assertThat(params.getRsiPeriod()).isEqualTo(7);
    }

    @Test
    public void createParameters_preservesThresholdPrecision() throws Exception {
        // Arrange
        double overboughtThreshold = 70.5;
        double oversoldThreshold = 29.5;

        Genotype<DoubleGene> genotype = Genotype.of(
            DoubleChromosome.of(DoubleGene.of(14.0, 5, 50)),
            DoubleChromosome.of(DoubleGene.of(7.0, 2, 30)),
            DoubleChromosome.of(DoubleGene.of(overboughtThreshold, 60, 85)),
            DoubleChromosome.of(DoubleGene.of(oversoldThreshold, 15, 40))
        );

        // Act
        SmaRsiParameters params = config.createParameters(genotype).unpack(SmaRsiParameters.class);

        // Assert
        assertThat(params.getOverboughtThreshold()).isEqualTo(overboughtThreshold);
        assertThat(params.getOversoldThreshold()).isEqualTo(oversoldThreshold);
    }
}
