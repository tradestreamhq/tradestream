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
import com.verlumen.tradestream.backtesting.BacktestRequest;
import com.verlumen.tradestream.backtesting.BacktestRequestFactory;
import com.verlumen.tradestream.backtesting.BacktestRequestFactoryImpl;
import com.verlumen.tradestream.backtesting.BacktestResult;
import com.verlumen.tradestream.backtesting.BacktestRunner;
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
public class FitnessFunctionFactoryImplTest {
  private static final ImmutableList<Candle> CANDLES =
      ImmutableList.of(
          Candle.newBuilder().setOpen(100.0).setClose(105.0).setHigh(110).setLow(95).build());
  private static final StrategyType STRATEGY_TYPE = StrategyType.SMA_RSI;
  private static final String STRATEGY_NAME = "SMA_RSI";

  @Rule public MockitoRule mockitoRule = MockitoJUnit.rule();

  @Bind private BacktestRequestFactory backtestRequestFactory;
  @Bind @Mock private BacktestRunner mockBacktestRunner;
  @Bind @Mock private GenotypeConverter mockGenotypeConverter;

  @Inject private FitnessFunctionFactoryImpl fitnessFunctionFactory;

  private Genotype<?> testGenotype;

  @Before
  public void setUp() throws Exception {
    // Setup
    backtestRequestFactory = new BacktestRequestFactoryImpl();
    testGenotype = Genotype.of(DoubleChromosome.of(0.0, 1.0));
    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }

  // Tests using the new string-based API
  @Test
  public void create_withStrategyName_validGenotype_returnsStrategyScore() throws Exception {
    // Arrange: Setup mock behavior
    double expectedScore = 0.85;
    BacktestResult mockBacktestResult =
        BacktestResult.newBuilder().setStrategyScore(expectedScore).build();
    when(mockBacktestRunner.runBacktest(any(BacktestRequest.class))).thenReturn(mockBacktestResult);
    when(mockGenotypeConverter.convertToParameters(any(Genotype.class), any(String.class)))
        .thenReturn(Any.getDefaultInstance()); // Return a dummy Any

    // Act: Create the fitness function using string-based API
    var fitnessFunction = fitnessFunctionFactory.create(STRATEGY_NAME, CANDLES);
    double actualScore = fitnessFunction.apply(testGenotype);

    // Assert: Check the return value
    assertThat(actualScore).isEqualTo(expectedScore);
  }

  @Test
  public void create_withStrategyName_backtestRunnerThrowsException_returnsNegativeInfinity()
      throws Exception {
    // Arrange: Configure the mock to throw an exception
    when(mockBacktestRunner.runBacktest(any(BacktestRequest.class)))
        .thenThrow(new RuntimeException("Simulated error"));
    when(mockGenotypeConverter.convertToParameters(any(Genotype.class), any(String.class)))
        .thenReturn(Any.getDefaultInstance());

    // Act: Create the fitness function using string-based API
    var fitnessFunction = fitnessFunctionFactory.create(STRATEGY_NAME, CANDLES);
    double score = fitnessFunction.apply(testGenotype);

    // Assert: Expect the lowest possible fitness score
    assertThat(score).isEqualTo(Double.NEGATIVE_INFINITY);
  }

  @Test
  public void create_withStrategyName_genotypeConverterThrowsException_returnsNegativeInfinity()
      throws Exception {
    // Arrange: Configure the mock to throw an exception
    when(mockGenotypeConverter.convertToParameters(any(Genotype.class), any(String.class)))
        .thenThrow(new RuntimeException("Simulated conversion error"));

    // Act: Create the fitness function using string-based API
    var fitnessFunction = fitnessFunctionFactory.create(STRATEGY_NAME, CANDLES);
    double score = fitnessFunction.apply(testGenotype);

    // Assert: Expect the lowest possible fitness score
    assertThat(score).isEqualTo(Double.NEGATIVE_INFINITY);
  }

  @Test
  public void create_withInvalidStrategyName_returnsNegativeInfinity() throws Exception {
    // Act: Create the fitness function with an invalid strategy name
    var fitnessFunction = fitnessFunctionFactory.create("INVALID_STRATEGY", CANDLES);
    double score = fitnessFunction.apply(testGenotype);

    // Assert: Expect the lowest possible fitness score (IllegalArgumentException from valueOf)
    assertThat(score).isEqualTo(Double.NEGATIVE_INFINITY);
  }

  // Tests using the deprecated enum-based API (for backwards compatibility)
  @SuppressWarnings("deprecation")
  @Test
  public void create_withStrategyType_validGenotype_returnsStrategyScore() throws Exception {
    // Arrange: Setup mock behavior
    double expectedScore = 0.85;
    BacktestResult mockBacktestResult =
        BacktestResult.newBuilder().setStrategyScore(expectedScore).build();
    when(mockBacktestRunner.runBacktest(any(BacktestRequest.class))).thenReturn(mockBacktestResult);
    when(mockGenotypeConverter.convertToParameters(any(Genotype.class), any(String.class)))
        .thenReturn(Any.getDefaultInstance()); // Return a dummy Any

    // Act: Create the fitness function using deprecated enum-based API
    var fitnessFunction = fitnessFunctionFactory.create(STRATEGY_TYPE, CANDLES);
    double actualScore = fitnessFunction.apply(testGenotype);

    // Assert: Check the return value
    assertThat(actualScore).isEqualTo(expectedScore);
  }

  @SuppressWarnings("deprecation")
  @Test
  public void create_withStrategyType_backtestRunnerThrowsException_returnsNegativeInfinity()
      throws Exception {
    // Arrange: Configure the mock to throw an exception
    when(mockBacktestRunner.runBacktest(any(BacktestRequest.class)))
        .thenThrow(new RuntimeException("Simulated error"));
    when(mockGenotypeConverter.convertToParameters(any(Genotype.class), any(String.class)))
        .thenReturn(Any.getDefaultInstance());

    // Act: Create the fitness function using deprecated enum-based API
    var fitnessFunction = fitnessFunctionFactory.create(STRATEGY_TYPE, CANDLES);
    double score = fitnessFunction.apply(testGenotype);

    // Assert: Expect the lowest possible fitness score
    assertThat(score).isEqualTo(Double.NEGATIVE_INFINITY);
  }

  @SuppressWarnings("deprecation")
  @Test
  public void create_withStrategyType_genotypeConverterThrowsException_returnsNegativeInfinity()
      throws Exception {
    // Arrange: Configure the mock to throw an exception
    when(mockGenotypeConverter.convertToParameters(any(Genotype.class), any(String.class)))
        .thenThrow(new RuntimeException("Simulated conversion error"));

    // Act: Create the fitness function using deprecated enum-based API
    var fitnessFunction = fitnessFunctionFactory.create(STRATEGY_TYPE, CANDLES);
    double score = fitnessFunction.apply(testGenotype);

    // Assert: Expect the lowest possible fitness score
    assertThat(score).isEqualTo(Double.NEGATIVE_INFINITY);
  }

  // Edge Case: Empty Candle List (this should also be covered in BacktestRunner tests)
  @Test
  public void create_emptyCandles_returnsNegativeInfinity() throws Exception {
    // Arrange: Setup mock behavior
    when(mockGenotypeConverter.convertToParameters(any(Genotype.class), any(String.class)))
        .thenReturn(Any.getDefaultInstance());

    // Use a default return (e.g., throwing exception) for the backtestRunner.
    when(mockBacktestRunner.runBacktest(any(BacktestRequest.class)))
        .thenThrow(new IllegalArgumentException("Empty candles list"));

    // Act: Create the function and apply it
    var fitnessFunction = fitnessFunctionFactory.create(STRATEGY_NAME, ImmutableList.of());
    double score = fitnessFunction.apply(testGenotype);

    // Assert
    assertThat(score).isEqualTo(Double.NEGATIVE_INFINITY);
  }
}
