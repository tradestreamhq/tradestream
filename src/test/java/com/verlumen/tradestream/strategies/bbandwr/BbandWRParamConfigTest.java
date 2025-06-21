package com.verlumen.tradestream.strategies.bbandwr;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.BbandWRParameters;
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
public class BbandWRParamConfigTest {
  private BbandWRParamConfig config;

  @Before
  public void setUp() {
    config = new BbandWRParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(3);
  }

  @Test
  public void testCreateParameters_validChromosomes_returnsPackedParameters() {
    // Create chromosomes with correct parameter order
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(10, 50, 20), // Bollinger Bands Period
            IntegerChromosome.of(5, 30, 14), // Williams %R Period
            DoubleChromosome.of(1.5, 3.0, 2.0) // Standard Deviation Multiplier
            );

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(BbandWRParameters.class)).isTrue();
  }

  @Test
  public void testCreateParameters_invalidChromosomeSize_throwsException() {
    // Create only two chromosomes instead of three
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(10, 50, 20),
            IntegerChromosome.of(5, 30, 14)
        );

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class,
            () -> config.createParameters(ImmutableList.copyOf(chromosomes)));
    assertThat(thrown).hasMessageThat().contains("Expected 3 chromosomes but got 2");
  }

  @Test
  public void testInitialChromosomes_returnsExpectedSize() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(3);
  }

  @Test
  public void testChromosomeSpecs_haveCorrectRanges() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    
    // Bollinger Bands Period (10-50)
    assertThat(specs.get(0).getRange().lowerEndpoint()).isEqualTo(10);
    assertThat(specs.get(0).getRange().upperEndpoint()).isEqualTo(50);
    
    // Williams %R Period (5-30)
    assertThat(specs.get(1).getRange().lowerEndpoint()).isEqualTo(5);
    assertThat(specs.get(1).getRange().upperEndpoint()).isEqualTo(30);
    
    // Standard Deviation Multiplier (1.5-3.0)
    assertThat(specs.get(2).getRange().lowerEndpoint()).isEqualTo(1.5);
    assertThat(specs.get(2).getRange().upperEndpoint()).isEqualTo(3.0);
  }

  @Test
  public void testCreateParameters_extractsCorrectValues() throws Exception {
    // Create chromosomes with specific values
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(10, 50, 25), // Bollinger Bands Period
            IntegerChromosome.of(5, 30, 20), // Williams %R Period
            DoubleChromosome.of(1.5, 3.0, 2.5) // Standard Deviation Multiplier
            );

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    BbandWRParameters params = packedParams.unpack(BbandWRParameters.class);
    
    assertThat(params.getBbandsPeriod()).isEqualTo(25);
    assertThat(params.getWrPeriod()).isEqualTo(20);
    assertThat(params.getStdDevMultiplier()).isEqualTo(2.5);
  }
}
