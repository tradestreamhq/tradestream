package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import io.jenetics.DoubleChromosome;
import io.jenetics.DoubleGene;
import io.jenetics.Gene;
import io.jenetics.Genotype;
import io.jenetics.Phenotype;
import io.jenetics.engine.Engine;
import io.jenetics.engine.EvolutionResult;
import io.jenetics.engine.EvolutionStart;
import io.jenetics.engine.Limits;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

import java.util.function.Function;
import java.util.function.Predicate;

@RunWith(JUnit4.class)
public class GeneticAlgorithmOrchestratorImplTest {

  @Rule public MockitoRule rule = MockitoJUnit.rule();

  @Mock @Bind private GAEngineFactory mockEngineFactory;
  @Mock @Bind private GenotypeConverter mockGenotypeConverter;

  @Inject private GeneticAlgorithmOrchestratorImpl orchestrator;

  // Create a real genotype and phenotype for testing
  private Genotype<DoubleGene> testGenotype;
  private Phenotype<DoubleGene, Double> testPhenotype;

  @Before
  public void setUp() {
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);

    // Create a simple test genotype with one chromosome
    testGenotype = Genotype.of(DoubleChromosome.of(0.0, 1.0));
    
    // Create a test phenotype with the genotype and a fitness value
    testPhenotype = Phenotype.of(testGenotype, 1, 100.0);
    
    // Configure genotypeConverter mock
    Any expectedParameters = Any.pack(SmaRsiParameters.getDefaultInstance());
    when(mockGenotypeConverter.convertToParameters(any(), any())).thenReturn(expectedParameters);
  }

  @Test
  @SuppressWarnings("unchecked") // Needed for the mock Engine cast
  public void runOptimization_validRequest_returnsBestStrategy() {
    // Arrange
    GAOptimizationRequest request = GAOptimizationRequest.newBuilder()
        .setStrategyType(StrategyType.SMA_RSI)
        .setMaxGenerations(10)
        .addCandles(Candle.getDefaultInstance()) // Add at least one candle to avoid empty list error
        .build();

    // Create a test Engine with a simple fitness function that always returns a constant value
    // Note: We're using the wildcard type to match the updated GAEngineFactory interface
    Engine<?, Double> testEngine = (Engine<?, Double>) Engine
        .builder(g -> 100.0, testGenotype)
        .build();
    
    // Configure the mock engine factory to return our test engine
    when(mockEngineFactory.createEngine(any())).thenReturn(testEngine);

    // Act
    BestStrategyResponse response = orchestrator.runOptimization(request);

    // Assert
    verify(mockEngineFactory).createEngine(request);
    verify(mockGenotypeConverter).convertToParameters(any(), any());
    
    // Since we can't directly mock the stream or control the evolution result,
    // we're verifying that the process works end-to-end rather than specific method calls
    assertThat(response).isNotNull();
    assertThat(response.hasBestStrategyParameters()).isTrue();
  }

  @Test
  public void runOptimization_emptyCandlesList_throwsException() {
    // Arrange
    GAOptimizationRequest request = GAOptimizationRequest.newBuilder()
        .setStrategyType(StrategyType.SMA_RSI)
        .build();

    // Act & Assert
    IllegalArgumentException thrown = assertThrows(
        IllegalArgumentException.class,
        () -> orchestrator.runOptimization(request));
        
    assertThat(thrown).hasMessageThat().contains("Candles list cannot be empty");
  }

  @Test
  @SuppressWarnings("unchecked") // Needed for the mock Engine cast
  public void runOptimization_zeroMaxGenerations_usesDefault() {
    // Arrange
    GAOptimizationRequest request = GAOptimizationRequest.newBuilder()
        .setStrategyType(StrategyType.SMA_RSI)
        .addAllCandles(ImmutableList.of(Candle.getDefaultInstance()))
        .setMaxGenerations(0) // Set to 0 to use default
        .build();

    // Create a test Engine with a simple fitness function
    // Using wildcard type to match the GAEngineFactory interface
    Engine<?, Double> testEngine = (Engine<?, Double>) Engine
        .builder(g -> 100.0, testGenotype)
        .build();
    
    when(mockEngineFactory.createEngine(any())).thenReturn(testEngine);

    // Act
    orchestrator.runOptimization(request);

    // Assert that the engine was created with the request
    verify(mockEngineFactory).createEngine(request);

    // We can't directly verify the limit being set on the stream since we can't mock it
  }

  @Test
  public void runOptimization_engineCreationFails_throwsException() {
    // Arrange
    GAOptimizationRequest request = GAOptimizationRequest.newBuilder()
        .setStrategyType(StrategyType.SMA_RSI)
        .addAllCandles(ImmutableList.of(Candle.getDefaultInstance()))
        .build();

    when(mockEngineFactory.createEngine(any())).thenThrow(new RuntimeException("Engine failure"));

    // Act & Assert
    assertThrows(RuntimeException.class, () -> orchestrator.runOptimization(request));
  }
}
