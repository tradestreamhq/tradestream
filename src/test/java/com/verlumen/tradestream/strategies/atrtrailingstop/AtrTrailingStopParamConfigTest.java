package com.verlumen.tradestream.strategies.atrtrailingstop;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.AtrTrailingStopParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class AtrTrailingStopParamConfigTest {
  private AtrTrailingStopParamConfig config;

  @Before
  public void setUp() {
    config = new AtrTrailingStopParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(2);
    
    // ATR Period: range 5-30
    assertThat(specs.get(0).getRange().lowerEndpoint()).isEqualTo(5);
    assertThat(specs.get(0).getRange().upperEndpoint()).isEqualTo(30);
    
    // Multiplier: range 1.0-5.0
    assertThat(specs.get(1).getRange().lowerEndpoint()).isEqualTo(1.0);
    assertThat(specs.get(1).getRange().upperEndpoint()).isEqualTo(5.0);
  }

  @Test
  public void testCreateParameters_validChromosomes_returnsPackedParameters() {
    // Create chromosomes with correct parameter order: min, max, value
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(5, 30, 14), // ATR Period
            DoubleChromosome.of(1.0, 5.0, 2.0) // Multiplier
        );

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(AtrTrailingStopParameters.class)).isTrue();
  }

  @Test
  public void testCreateParameters_invalidChromosomeSize_throwsException() {
    // Create a single chromosome
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(IntegerChromosome.of(5, 30, 14)); // Only one chromosome

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
    assertThat(chromosomes.get(0)).isInstanceOf(IntegerChromosome.class);
    assertThat(chromosomes.get(1)).isInstanceOf(DoubleChromosome.class);
  }

  @Test
  public void testGetStrategyType_returnsExpectedType() {
    assertThat(config.getStrategyType()).isEqualTo(StrategyType.ATR_TRAILING_STOP);
  }

  @Test
  public void testCreateParameters_extractsCorrectValues() throws Exception {
    // Create chromosomes with specific values
    IntegerChromosome atrPeriodChrom = IntegerChromosome.of(5, 30, 20);
    DoubleChromosome multiplierChrom = DoubleChromosome.of(1.0, 5.0, 2.5);

    List<NumericChromosome<?, ?>> chromosomes = List.of(atrPeriodChrom, multiplierChrom);

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    AtrTrailingStopParameters params = packedParams.unpack(AtrTrailingStopParameters.class);

    assertThat(params.getAtrPeriod()).isEqualTo(20);
    assertThat(params.getMultiplier()).isEqualTo(2.5);
  }
}
