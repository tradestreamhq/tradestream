package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.discovery.ChromosomeSpec;
import com.verlumen.tradestream.strategies.ConfigurableStrategyParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Test;

/**
 * Tests for ConfigurableParamConfig verifying correct chromosome spec generation and parameter
 * creation.
 */
public class ConfigurableParamConfigTest {

  @Test
  public void testChromosomeSpecsForIntegerParams() {
    StrategyConfig config =
        StrategyConfig.builder()
            .name("TEST")
            .parameters(
                List.of(
                    ParameterDefinition.builder()
                        .name("period1")
                        .type(ParameterType.INTEGER)
                        .min(5)
                        .max(50)
                        .defaultValue(20)
                        .build(),
                    ParameterDefinition.builder()
                        .name("period2")
                        .type(ParameterType.INTEGER)
                        .min(10)
                        .max(100)
                        .defaultValue(50)
                        .build()))
            .build();

    ConfigurableParamConfig paramConfig = new ConfigurableParamConfig(config);
    ImmutableList<ChromosomeSpec<?>> specs = paramConfig.getChromosomeSpecs();

    assertEquals("Should have 2 chromosome specs", 2, specs.size());

    // Check ranges
    ChromosomeSpec<Integer> spec1 = (ChromosomeSpec<Integer>) specs.get(0);
    assertTrue("First spec should include 5", spec1.getRange().contains(5));
    assertTrue("First spec should include 50", spec1.getRange().contains(50));

    ChromosomeSpec<Integer> spec2 = (ChromosomeSpec<Integer>) specs.get(1);
    assertTrue("Second spec should include 10", spec2.getRange().contains(10));
    assertTrue("Second spec should include 100", spec2.getRange().contains(100));
  }

  @Test
  public void testChromosomeSpecsForDoubleParams() {
    StrategyConfig config =
        StrategyConfig.builder()
            .name("TEST")
            .parameters(
                List.of(
                    ParameterDefinition.builder()
                        .name("multiplier")
                        .type(ParameterType.DOUBLE)
                        .min(0.5)
                        .max(3.0)
                        .defaultValue(2.0)
                        .build()))
            .build();

    ConfigurableParamConfig paramConfig = new ConfigurableParamConfig(config);
    ImmutableList<ChromosomeSpec<?>> specs = paramConfig.getChromosomeSpecs();

    assertEquals("Should have 1 chromosome spec", 1, specs.size());

    ChromosomeSpec<Double> spec = (ChromosomeSpec<Double>) specs.get(0);
    assertTrue("Spec should include 0.5", spec.getRange().contains(0.5));
    assertTrue("Spec should include 3.0", spec.getRange().contains(3.0));
  }

  @Test
  public void testMixedParameterTypes() {
    StrategyConfig config =
        StrategyConfig.builder()
            .name("TEST")
            .parameters(
                List.of(
                    ParameterDefinition.builder()
                        .name("period")
                        .type(ParameterType.INTEGER)
                        .min(5)
                        .max(50)
                        .defaultValue(20)
                        .build(),
                    ParameterDefinition.builder()
                        .name("multiplier")
                        .type(ParameterType.DOUBLE)
                        .min(1.0)
                        .max(3.0)
                        .defaultValue(2.0)
                        .build()))
            .build();

    ConfigurableParamConfig paramConfig = new ConfigurableParamConfig(config);
    ImmutableList<ChromosomeSpec<?>> specs = paramConfig.getChromosomeSpecs();

    assertEquals("Should have 2 chromosome specs", 2, specs.size());
  }

  @Test
  public void testCreateParametersFromChromosomes() throws InvalidProtocolBufferException {
    StrategyConfig config =
        StrategyConfig.builder()
            .name("TEST")
            .parameters(
                List.of(
                    ParameterDefinition.builder()
                        .name("period")
                        .type(ParameterType.INTEGER)
                        .min(5)
                        .max(50)
                        .defaultValue(20)
                        .build(),
                    ParameterDefinition.builder()
                        .name("multiplier")
                        .type(ParameterType.DOUBLE)
                        .min(1.0)
                        .max(3.0)
                        .defaultValue(2.0)
                        .build()))
            .build();

    ConfigurableParamConfig paramConfig = new ConfigurableParamConfig(config);

    // Create test chromosomes
    IntegerChromosome intChrom = IntegerChromosome.of(5, 50);
    DoubleChromosome doubleChrom = DoubleChromosome.of(1.0, 3.0);

    ImmutableList<NumericChromosome<?, ?>> chromosomes = ImmutableList.of(intChrom, doubleChrom);

    Any anyParams = paramConfig.createParameters(chromosomes);
    ConfigurableStrategyParameters params = anyParams.unpack(ConfigurableStrategyParameters.class);

    assertTrue("Should have period parameter", params.containsIntValues("period"));
    assertTrue("Should have multiplier parameter", params.containsDoubleValues("multiplier"));

    // Values should be within range
    int period = params.getIntValuesOrThrow("period");
    assertTrue("Period should be >= 5", period >= 5);
    assertTrue("Period should be <= 50", period <= 50);

    double multiplier = params.getDoubleValuesOrThrow("multiplier");
    assertTrue("Multiplier should be >= 1.0", multiplier >= 1.0);
    assertTrue("Multiplier should be <= 3.0", multiplier <= 3.0);
  }

  @Test
  public void testInitialChromosomes() {
    StrategyConfig config =
        StrategyConfig.builder()
            .name("TEST")
            .parameters(
                List.of(
                    ParameterDefinition.builder()
                        .name("period1")
                        .type(ParameterType.INTEGER)
                        .min(5)
                        .max(50)
                        .defaultValue(20)
                        .build(),
                    ParameterDefinition.builder()
                        .name("period2")
                        .type(ParameterType.INTEGER)
                        .min(10)
                        .max(100)
                        .defaultValue(50)
                        .build()))
            .build();

    ConfigurableParamConfig paramConfig = new ConfigurableParamConfig(config);
    ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = paramConfig.initialChromosomes();

    assertEquals("Should have 2 initial chromosomes", 2, chromosomes.size());
    assertTrue(
        "First should be IntegerChromosome", chromosomes.get(0) instanceof IntegerChromosome);
    assertTrue(
        "Second should be IntegerChromosome", chromosomes.get(1) instanceof IntegerChromosome);
  }

  @Test
  public void testEmptyParameters() {
    StrategyConfig config = StrategyConfig.builder().name("TEST").parameters(List.of()).build();

    ConfigurableParamConfig paramConfig = new ConfigurableParamConfig(config);
    ImmutableList<ChromosomeSpec<?>> specs = paramConfig.getChromosomeSpecs();

    assertTrue("Empty config should have no specs", specs.isEmpty());
  }

  @Test(expected = IllegalArgumentException.class)
  public void testChromosomeCountMismatch() {
    StrategyConfig config =
        StrategyConfig.builder()
            .name("TEST")
            .parameters(
                List.of(
                    ParameterDefinition.builder()
                        .name("period")
                        .type(ParameterType.INTEGER)
                        .min(5)
                        .max(50)
                        .defaultValue(20)
                        .build()))
            .build();

    ConfigurableParamConfig paramConfig = new ConfigurableParamConfig(config);

    // Try to create parameters with wrong number of chromosomes
    ImmutableList<NumericChromosome<?, ?>> chromosomes =
        ImmutableList.of(
            IntegerChromosome.of(5, 50), IntegerChromosome.of(5, 50)); // Extra chromosome

    paramConfig.createParameters(chromosomes);
  }
}
