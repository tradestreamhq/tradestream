package com.verlumen.tradestream.strategies.atrcci;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.AtrCciParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class AtrCciParamConfigTest {
  private AtrCciParamConfig config;

  @Before
  public void setUp() {
    config = new AtrCciParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(2);
    // ATR Period: range 5-30
    assertThat(specs.get(0).getRange().lowerEndpoint()).isEqualTo(5);
    assertThat(specs.get(0).getRange().upperEndpoint()).isEqualTo(30);
    // CCI Period: range 10-50
    assertThat(specs.get(1).getRange().lowerEndpoint()).isEqualTo(10);
    assertThat(specs.get(1).getRange().upperEndpoint()).isEqualTo(50);
  }

  @Test
  public void testCreateParameters_validChromosomes_returnsPackedParameters() {
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(5, 30, 14), // ATR Period
            IntegerChromosome.of(10, 50, 20) // CCI Period
            );

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(AtrCciParameters.class)).isTrue();
  }

  @Test
  public void testCreateParameters_invalidChromosomeSize_throwsException() {
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
    assertThat(chromosomes.get(1)).isInstanceOf(IntegerChromosome.class);
  }

  @Test
  public void testCreateParameters_extractsValuesInCorrectRanges() throws Exception {
    // Create chromosomes and extract their actual values for testing
    IntegerChromosome atrPeriodChrom = IntegerChromosome.of(5, 30, 1);
    IntegerChromosome cciPeriodChrom = IntegerChromosome.of(10, 50, 1);

    List<NumericChromosome<?, ?>> chromosomes = List.of(atrPeriodChrom, cciPeriodChrom);

    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    AtrCciParameters params = packedParams.unpack(AtrCciParameters.class);

    // Extract the actual values from chromosomes
    int expectedAtrPeriod = atrPeriodChrom.gene().allele();
    int expectedCciPeriod = cciPeriodChrom.gene().allele();

    assertThat(params.getAtrPeriod()).isEqualTo(expectedAtrPeriod);
    assertThat(params.getCciPeriod()).isEqualTo(expectedCciPeriod);
    // Also verify values are within expected ranges
    assertThat(params.getAtrPeriod()).isAtLeast(5);
    assertThat(params.getAtrPeriod()).isAtMost(30);
    assertThat(params.getCciPeriod()).isAtLeast(10);
    assertThat(params.getCciPeriod()).isAtMost(50);
  }
}
