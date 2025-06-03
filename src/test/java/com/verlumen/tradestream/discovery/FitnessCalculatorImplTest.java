package com.verlumen.tradestream.discovery;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.backtesting.BacktestRequest;
import com.verlumen.tradestream.backtesting.BacktestRequestFactory;
import com.verlumen.tradestream.backtesting.BacktestRequestFactoryImpl;
import com.verlumen.tradestream.backtesting.BacktestResult;
import com.verlumen.tradestream.backtesting.BacktestRunner;
import com.verlumen.tradestream.backtesting.GAfitnessCalculationParams;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.DoubleChromosome;
import io.jenetics.Genotype;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

@RunWith(JUnit4.class)
public class FitnessCalculatorImplTest {
  @Rule public MockitoRule mockitoRule = MockitoJUnit.rule();

  @Bind private BacktestRequestFactory backtestRequestFactory;
  @Bind @Mock private BacktestRunner mockBacktestRunner;
  @Bind @Mock private GenotypeConverter mockGenotypeConverter;
  @Bind private FitnessCalculationParams fitnessCalculationParams;

  @Inject private FitnessCalculatorImpl fitnessCalculator;

  private Genotype<?> testGenotype;

  @Before
  public void setUp() throws Exception {
    // Setup
    backtestRequestFactory = new BacktestRequestFactoryImpl();
    fitnessCalculationParams =
        new FitnessCalculationParams(StrategyType.SMA_RSI, ImmutableList.of(
          Candle.newBuilder()
              .setOpen(100.0)
              .setClose(105.0)
              .setHigh(110)
              .setLow(95)
              .build()));

    testGenotype = Genotype.of(DoubleChromosome.of(0.0, 1.0));
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  @Test
  public void createFitnessFunction_validGenotype_returnsStrategyScore() throws Exception {
    // Arrange: Setup mock behavior
    double expectedScore = 0.85;
    BacktestResult mockBacktestResult =
        BacktestResult.newBuilder().setStrategyScore(expectedScore).build();
    when(mockBacktestRunner.runBacktest(any(BacktestRequest.class))).thenReturn(mockBacktestResult);
    when(mockGenotypeConverter.convertToParameters(any(Genotype.class), any(StrategyType.class)))
        .thenReturn(Any.getDefaultInstance()); // Return a dummy Any

    // Act: Create the fitness function and apply it to a test genotype
    var fitnessFunction = fitnessCalculator.createFitnessFunction(fitnessCalculationParams);
    double actualScore = fitnessFunction.apply(testGenotype);

    // Assert: Check the return value
    assertThat(actualScore).isEqualTo(expectedScore);
  }

  @Test
  public void createFitnessFunction_backtestRunnerThrowsException_returnsNegativeInfinity()
      throws Exception {
    // Arrange: Configure the mock to throw an exception
    when(mockBacktestRunner.runBacktest(any(BacktestRequest.class)))
        .thenThrow(new RuntimeException("Simulated error"));
    when(mockGenotypeConverter.convertToParameters(any(Genotype.class), any(StrategyType.class)))
        .thenReturn(Any.getDefaultInstance());

    // Act: Create the fitness function and apply it
    var fitnessFunction = fitnessCalculator.createFitnessFunction(fitnessCalculationParams);
    double score = fitnessFunction.apply(testGenotype);

    // Assert: Expect the lowest possible fitness score
    assertThat(score).isEqualTo(Double.NEGATIVE_INFINITY);
  }

  @Test
  public void createFitnessFunction_genotypeConverterThrowsException_returnsNegativeInfinity()
      throws Exception {
    // Arrange: Configure the mock to throw an exception
    when(mockGenotypeConverter.convertToParameters(any(Genotype.class), any(StrategyType.class)))
        .thenThrow(new RuntimeException("Simulated conversion error"));

    // Act: Create the fitness function and apply it
    var fitnessFunction = fitnessCalculator.createFitnessFunction(fitnessCalculationParams);
    double score = fitnessFunction.apply(testGenotype);

    // Assert: Expect the lowest possible fitness score
    assertThat(score).isEqualTo(Double.NEGATIVE_INFINITY);
  }

  // Edge Case: Empty Candle List (this should also be covered in BacktestRunner tests)
  @Test
  public void createFitnessFunction_emptyCandles_returnsNegativeInfinity() throws Exception {
    // Arrange: Create a request with an empty candle list
    GAfitnessCalculationParams emptyRequest =
        GAfitnessCalculationParams.newBuilder()
            .setStrategyType(StrategyType.SMA_RSI)
            .clearCandles() // Explicitly clear candles
            .build();

    when(mockGenotypeConverter.convertToParameters(any(Genotype.class), any(StrategyType.class)))
        .thenReturn(Any.getDefaultInstance());

    // Use a default return (e.g., throwing exception) for the backtestRunner.
    when(mockBacktestRunner.runBacktest(any(BacktestRequest.class)))
        .thenThrow(new IllegalArgumentException("Empty candles list"));

    // Act: Create the function and apply it
    var fitnessFunction = fitnessCalculator.createFitnessFunction(emptyRequest);
    double score = fitnessFunction.apply(testGenotype);

    // Assert
    assertThat(score).isEqualTo(Double.NEGATIVE_INFINITY);
  }
}
