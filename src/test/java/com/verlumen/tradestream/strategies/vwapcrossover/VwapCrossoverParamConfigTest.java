package com.verlumen.tradestream.strategies.vwapcrossover;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.VwapCrossoverParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class VwapCrossoverParamConfigTest {
  private VwapCrossoverParamConfig config;

  @Before
  public void setUp() {
    config = new VwapCrossoverParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(2);
    
    // VWAP Period (10-50)
    assertThat(specs.get(0).getRange().lowerEndpoint()).isEqualTo(10);
    assertThat(specs.get(0).getRange().upperEndpoint()).isEqualTo(50);
    
    // Moving Average Period (10-50)
    assertThat(specs.get(1).getRange().lowerEndpoint()).isEqualTo(10);
    assertThat(specs.get(1).getRange().upperEndpoint()).isEqualTo(50);
  }

  @Test
  public void testCreateParameters_validChromosomes_returnsPackedParameters() {
    // Create chromosomes with correct parameter order: min, max, value
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(10, 50, 20), // VWAP Period
            IntegerChromosome.of(10, 50, 25)  // Moving Average Period
        );

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(VwapCrossoverParameters.class)).isTrue();
    
    try {
      VwapCrossoverParameters params = packedParams.unpack(VwapCrossoverParameters.class);
      assertThat(params.getVwapPeriod()).isEqualTo(20);
      assertThat(params.getMovingAveragePeriod()).isEqualTo(25);
    } catch (Exception e) {
      throw new RuntimeException("Failed to unpack parameters", e);
    }
  }

  @Test
  public void testCreateParameters_invalidChromosomeSize_throwsException() {
    // Create a single chromosome when 2 are expected
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(IntegerChromosome.of(10, 50, 20)); // Only one chromosome

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class,
            () -> config.createParameters(ImmutableList.copyOf(chromosomes)));
    assertThat(thrown).hasMessageThat().contains("Expected 2 chromosomes but got 1");
  }

  @Test
  public void testInitialChromosomes_returnsExpectedSize() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(2);
    
    // Verify all chromosomes are IntegerChromosome
    assertThat(chromosomes.get(0)).isInstanceOf(IntegerChromosome.class);
    assertThat(chromosomes.get(1)).isInstanceOf(IntegerChromosome.class);
    
    // Verify ranges
    IntegerChromosome vwapPeriod = (IntegerChromosome) chromosomes.get(0);
    assertThat(vwapPeriod.gene().min()).isEqualTo(10);
    assertThat(vwapPeriod.gene().max()).isEqualTo(50);
    
    IntegerChromosome maPeriod = (IntegerChromosome) chromosomes.get(1);
    assertThat(maPeriod.gene().min()).isEqualTo(10);
    assertThat(maPeriod.gene().max()).isEqualTo(50);
  }
}
