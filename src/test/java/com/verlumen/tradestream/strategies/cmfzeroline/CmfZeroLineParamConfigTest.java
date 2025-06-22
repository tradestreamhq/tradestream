package com.verlumen.tradestream.strategies.cmfzeroline;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.CmfZeroLineParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;

public class CmfZeroLineParamConfigTest {
  private CmfZeroLineParamConfig config;

  @Before
  public void setUp() {
    config = new CmfZeroLineParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(1);
  }

  @Test
  public void testCreateParameters() {
    List<NumericChromosome<?, ?>> chromosomes = List.of(IntegerChromosome.of(10, 50, 20));
    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(CmfZeroLineParameters.class)).isTrue();
  }

  @Test
  public void testCreateParameters_invalidChromosomeSize_throwsException() {
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(IntegerChromosome.of(10, 50, 20), IntegerChromosome.of(10, 50, 20));
    assertThrows(
        IllegalArgumentException.class,
        () -> config.createParameters(ImmutableList.copyOf(chromosomes)));
  }

  @Test
  public void testInitialChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(1);
  }
}
