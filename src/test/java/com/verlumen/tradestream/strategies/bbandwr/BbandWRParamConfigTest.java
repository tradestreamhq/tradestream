package com.verlumen.tradestream.strategies.bbandwr;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.BbandWRParameters;
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
            IntegerChromosome.of(10, 50, 1), // Bollinger Bands Period
            IntegerChromosome.of(5, 30, 1), // Williams %R Period
            DoubleChromosome.of(1.5, 3.0, 1) // Standard Deviation Multiplier
            );

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(BbandWRParameters.class)).isTrue();
  }

  @Test
  public void testCreateParameters_invalidChromosomeSize_throwsException() {
    // Create only two chromosomes instead of three
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(IntegerChromosome.of(10, 50, 1), IntegerChromosome.of(5, 30, 1));

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
    // Create chromosomes with single genes each
    IntegerChromosome bbandsPeriodChrom = IntegerChromosome.of(10, 50, 1);
    IntegerChromosome wrPeriodChrom = IntegerChromosome.of(5, 30, 1);
    DoubleChromosome stdDevMultiplierChrom = DoubleChromosome.of(1.5, 3.0, 1);

    List<NumericChromosome<?, ?>> chromosomes =
        List.of(bbandsPeriodChrom, wrPeriodChrom, stdDevMultiplierChrom);

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    BbandWRParameters params = packedParams.unpack(BbandWRParameters.class);
    // Extract the actual values from chromosomes
    int expectedBbandsPeriod = bbandsPeriodChrom.gene().allele();
    int expectedWrPeriod = wrPeriodChrom.gene().allele();
    double expectedStdDevMultiplier = stdDevMultiplierChrom.gene().allele();
    assertThat(params.getBbandsPeriod()).isEqualTo(expectedBbandsPeriod);
    assertThat(params.getWrPeriod()).isEqualTo(expectedWrPeriod);
    assertThat(params.getStdDevMultiplier()).isEqualTo(expectedStdDevMultiplier);
    // Also verify values are within expected ranges
    assertThat(params.getBbandsPeriod()).isAtLeast(10);
    assertThat(params.getBbandsPeriod()).isAtMost(50);
    assertThat(params.getWrPeriod()).isAtLeast(5);
    assertThat(params.getWrPeriod()).isAtMost(30);
    assertThat(params.getStdDevMultiplier()).isAtLeast(1.5);
    assertThat(params.getStdDevMultiplier()).isAtMost(3.0);
  }
}
