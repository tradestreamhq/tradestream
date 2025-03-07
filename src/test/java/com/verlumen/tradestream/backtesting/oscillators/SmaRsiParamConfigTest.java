package com.verlumen.tradestream.backtesting.oscillators;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.backtesting.ChromosomeSpec;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
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
  public void getChromosomeSpecs_returnsExpectedRanges() {
    // Act
    List<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();

    // Assert
    assertThat(specs).hasSize(4); // 4 parameters: MA period, RSI period, Overbought, Oversold

    // Moving Average Period (5-50)
    assertThat(specs.get(0).getRange().lowerEndpoint()).isEqualTo(5);
    assertThat(specs.get(0).getRange().upperEndpoint()).isEqualTo(50);

    // RSI Period (2-30)
    assertThat(specs.get(1).getRange().lowerEndpoint()).isEqualTo(2);
    assertThat(specs.get(1).getRange().upperEndpoint()).isEqualTo(30);

    // Overbought Threshold (60.0-85.0)
    assertThat(specs.get(2).getRange().lowerEndpoint()).isEqualTo(60.0);
    assertThat(specs.get(2).getRange().upperEndpoint()).isEqualTo(85.0);

    // Oversold Threshold (15.0-40.0)
    assertThat(specs.get(3).getRange().lowerEndpoint()).isEqualTo(15.0);
    assertThat(specs.get(3).getRange().upperEndpoint()).isEqualTo(40.0);
  }

  @Test
  public void createParameters_convertsChromosomesCorrectly() throws Exception {
    // Create chromosomes matching our specs (single gene each, random allele in given range)
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = ImmutableList.of(
        IntegerChromosome.of(5, 50, 1),   // movingAveragePeriod
        IntegerChromosome.of(2, 30, 1),   // rsiPeriod
        DoubleChromosome.of(60.0, 85.0),  // overboughtThreshold
        DoubleChromosome.of(15.0, 40.0)   // oversoldThreshold
    );

    // Act
    SmaRsiParameters params = config.createParameters(chromosomes).unpack(SmaRsiParameters.class);

    // Assert
    // Instead of asserting exact values, verify they fall within the specified bounds.
    assertThat(params.getMovingAveragePeriod()).isAtLeast(5);
    assertThat(params.getMovingAveragePeriod()).isAtMost(50);

    assertThat(params.getRsiPeriod()).isAtLeast(2);
    assertThat(params.getRsiPeriod()).isAtMost(30);

    assertThat(params.getOverboughtThreshold()).isAtLeast(60.0);
    assertThat(params.getOverboughtThreshold()).isAtMost(85.0);

    assertThat(params.getOversoldThreshold()).isAtLeast(15.0);
    assertThat(params.getOversoldThreshold()).isAtMost(40.0);
  }

  @Test
  public void initialChromosomes_matchesSpecs() {
    // Act
    var chromosomes = config.initialChromosomes();

    // Assert
    assertThat(chromosomes).hasSize(4);
    assertThat(chromosomes.get(0)).isInstanceOf(IntegerChromosome.class);
    assertThat(chromosomes.get(1)).isInstanceOf(IntegerChromosome.class);
    assertThat(chromosomes.get(2)).isInstanceOf(DoubleChromosome.class);
    assertThat(chromosomes.get(3)).isInstanceOf(DoubleChromosome.class);

    // Verify ranges
    IntegerChromosome maPeriod = (IntegerChromosome) chromosomes.get(0);
    assertThat(maPeriod.gene().min()).isEqualTo(5);
    assertThat(maPeriod.gene().max()).isEqualTo(50);

    DoubleChromosome overbought = (DoubleChromosome) chromosomes.get(2);
    assertThat(overbought.gene().min()).isEqualTo(60.0);
    assertThat(overbought.gene().max()).isEqualTo(85.0);
  }
}
