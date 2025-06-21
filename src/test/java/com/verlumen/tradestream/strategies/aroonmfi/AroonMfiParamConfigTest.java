package com.verlumen.tradestream.strategies.aroonmfi;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.AroonMfiParameters;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;

public class AroonMfiParamConfigTest {
  private AroonMfiParamConfig config;

  @Before
  public void setUp() {
    config = new AroonMfiParamConfig();
  }

  @Test
  public void testGetChromosomeSpecs() {
    ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
    assertThat(specs).hasSize(4);
  }

  @Test
  public void testCreateParameters() {
    List<NumericChromosome<?, ?>> chromosomes =
        List.of(
            IntegerChromosome.of(10, 50, 25), // Aroon Period
            IntegerChromosome.of(10, 50, 14), // MFI Period
            IntegerChromosome.of(60, 90, 80), // Overbought Threshold
            IntegerChromosome.of(10, 40, 20) // Oversold Threshold
            );
    Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
    assertThat(packedParams.is(AroonMfiParameters.class)).isTrue();
  }

  @Test
  public void testCreateParameters_invalidChromosomeSize_throwsException() {
    List<NumericChromosome<?, ?>> chromosomes = List.of(IntegerChromosome.of(10, 50, 25));
    assertThrows(
        IllegalArgumentException.class,
        () -> config.createParameters(ImmutableList.copyOf(chromosomes)));
  }

  @Test
  public void testInitialChromosomes() {
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
    assertThat(chromosomes).hasSize(4);
  }
}
