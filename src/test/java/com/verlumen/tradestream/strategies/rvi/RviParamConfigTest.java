package com.verlumen.tradestream.strategies.rvi;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.RviParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.IntegerGene;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class RviParamConfigTest {
  private RviParamConfig config;

  @Before
  public void setUp() {
    config = new RviParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs_returnsExpectedSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(1);
    // RVI Period (5-30)
    assertThat(specs.get(0).getRange().lowerEndpoint()).isEqualTo(5);
    assertThat(specs.get(0).getRange().upperEndpoint()).isEqualTo(30);
  }

  @Test
  public void testCreateParameters_validChromosomes_returnsPackedParameters() throws Exception {
    // Create chromosome with correct parameter order: min, max, value
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(IntegerGene.of(10, 5, 30)) // RVI Period
            );
    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(RviParameters.class)).isTrue();

    RviParameters params = packedParams.unpack(RviParameters.class);
    assertThat(params.getPeriod()).isEqualTo(10);
  }

  @Test
  public void testCreateParameters_invalidChromosomeSize_throwsException() {
    // Create multiple chromosomes when only one is expected
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(IntegerGene.of(10, 5, 30)), // RVI Period
            IntegerChromosome.of(IntegerGene.of(5, 1, 10)) // Extra chromosome
            );
    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class,
            () -> config.createParameters(ImmutableList.copyOf(chromosomes)));
    assertThat(thrown).hasMessageThat().contains("Expected 1 chromosomes but got 2");
  }

  @Test
  public void testInitialChromosomes_returnsExpectedSize() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(1);
    assertThat(chromosomes.get(0)).isInstanceOf(IntegerChromosome.class);
    // Verify range
    IntegerChromosome periodChromosome = (IntegerChromosome) chromosomes.get(0);
    assertThat(periodChromosome.min()).isEqualTo(5);
    assertThat(periodChromosome.max()).isEqualTo(30);
  }
}
