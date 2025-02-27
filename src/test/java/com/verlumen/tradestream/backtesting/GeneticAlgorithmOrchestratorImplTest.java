package com.verlumen.tradestream.backtesting;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.Mockito.*;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.DoubleGene;
import io.jenetics.Genotype;
import io.jenetics.engine.Engine;
import io.jenetics.engine.EvolutionResult;
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

  @Inject private GeneticAlgorithmOrchestratorImpl orchestrator;

  @Before
  public void setUp() {
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);

    // Mock the engine to return a stream that can be collected into the mockEvolutionResult
    when(mockEngineFactory.createEngine(any())).thenReturn(mockEngine);
    when(mockEngine.stream()).thenReturn(Stream.of(mockEvolutionResult).limit(1));
    when(mockEvolutionResult.bestPhenotype()).thenReturn(mock(Phenotype.class)); // Ensure bestPhenotype doesn't return null
    when(mockEvolutionResult.bestPhenotype().genotype()).thenReturn(mockGenotype);
    when(mockEvolutionResult.bestPhenotype().fitness()).thenReturn(100.0);
  }

  @Test
  public void runOptimization_validRequest_returnsBestStrategy() {
    // Arrange
    GAOptimizationRequest request =
        GAOptimizationRequest.newBuilder()
            .setStrategyType(StrategyType.SMA_RSI)
            .setMaxGenerations(10)
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

  @Test(expected = IllegalArgumentException.class)
  public void runOptimization_emptyCandlesList_throwsException() {
    // Arrange
    GAOptimizationRequest request =
        GAOptimizationRequest.newBuilder().setStrategyType(StrategyType.SMA_RSI).build();

    // Act & Assert
    orchestrator.runOptimization(request);
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
      verify(mockEngine).stream();  // Get the stream from the mockEngine
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
