package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.Mockito.*;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import io.jenetics.DoubleGene;
import io.jenetics.Genotype;
import io.jenetics.Phenotype;
import io.jenetics.engine.Engine;
import io.jenetics.engine.EvolutionResult;
import io.jenetics.engine.EvolutionStream;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class GeneticAlgorithmOrchestratorImplTest {

  @Rule public MockitoRule rule = MockitoJUnit.rule();

  @Mock @Bind private GAEngineFactory mockEngineFactory;

  @Mock @Bind private GenotypeConverter mockGenotypeConverter;

  @Mock private Engine<DoubleGene, Double> mockEngine;

  @Mock private EvolutionResult<DoubleGene, Double> mockEvolutionResult;
  
  @Mock private Genotype<DoubleGene> mockGenotype;
  
  @Mock private Phenotype<DoubleGene, Double> mockPhenotype;
  
  @Mock private EvolutionStream<DoubleGene, Double> mockEvolutionStream;

  @Inject private GeneticAlgorithmOrchestratorImpl orchestrator;

  @Before
  public void setUp() {
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);

    // Mock the engine to return a mock EvolutionStream
    when(mockEngineFactory.createEngine(any())).thenReturn(mockEngine);
    when(mockEngine.stream()).thenReturn(mockEvolutionStream);
    
    // Setup the mockEvolutionStream to be collectible into the best phenotype
    when(mockEvolutionStream.limit(anyInt())).thenReturn(mockEvolutionStream);
    when(mockEvolutionStream.collect(any())).thenReturn(mockPhenotype);
    
    when(mockPhenotype.genotype()).thenReturn(mockGenotype);
    when(mockPhenotype.fitness()).thenReturn(100.0);
  }

  @Test
  public void runOptimization_validRequest_returnsBestStrategy() {
    // Arrange
    GAOptimizationRequest request =
        GAOptimizationRequest.newBuilder()
            .setStrategyType(StrategyType.SMA_RSI)
            .setMaxGenerations(10)
            .addCandles(Candle.getDefaultInstance()) // Add at least one candle to avoid empty list error
            .build();

    Any expectedParameters = Any.pack(SmaRsiParameters.getDefaultInstance());
    when(mockGenotypeConverter.convertToParameters(any(), any())).thenReturn(expectedParameters);

    // Act
    BestStrategyResponse response = orchestrator.runOptimization(request);

    // Assert
    assertThat(response.getBestStrategyParameters()).isEqualTo(expectedParameters);
    assertThat(response.getBestScore()).isEqualTo(100.0);

    verify(mockEngineFactory).createEngine(request);
    verify(mockEngine).stream();
    verify(mockGenotypeConverter).convertToParameters(mockGenotype, StrategyType.SMA_RSI);
  }

  @Test
  public void runOptimization_emptyCandlesList_throwsException() {
    // Arrange
    GAOptimizationRequest request =
        GAOptimizationRequest.newBuilder().setStrategyType(StrategyType.SMA_RSI).build();

    // Act & Assert
    IllegalArgumentException thrown = assertThrows(
        IllegalArgumentException.class,
        () -> orchestrator.runOptimization(request));
        
    assertThat(thrown).hasMessageThat().contains("Candles list cannot be empty");
  }

  @Test
  public void runOptimization_zeroMaxGenerations_usesDefault() {
    // Arrange
      GAOptimizationRequest request =
          GAOptimizationRequest.newBuilder()
              .setStrategyType(StrategyType.SMA_RSI)
              .addAllCandles(ImmutableList.of(Candle.getDefaultInstance()))
              .setMaxGenerations(0) // Set to 0 to use default
              .build();

      // Act
      orchestrator.runOptimization(request);

      // Assert: Verify that the stream was limited by the DEFAULT_MAX_GENERATIONS (from GAConstants)
      verify(mockEngine).stream();
      verify(mockEvolutionStream).limit(GAConstants.DEFAULT_MAX_GENERATIONS);
  }

  @Test
  public void runOptimization_engineCreationFails_throwsException() {
    // Arrange
      GAOptimizationRequest request =
              GAOptimizationRequest.newBuilder()
                      .setStrategyType(StrategyType.SMA_RSI)
                      .addAllCandles(ImmutableList.of(Candle.getDefaultInstance()))
                      .build();

    when(mockEngineFactory.createEngine(any())).thenThrow(new RuntimeException("Engine failure"));

    // Act & Assert
    assertThrows(RuntimeException.class, () -> orchestrator.runOptimization(request));
  }
}
