package com.verlumen.tradestream.strategies;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

@RunWith(JUnit4.class)
public class StrategyManagerImplTest {
  @Mock private StrategyFactory<SmaRsiParameters> mockSmaRsiFactory;

  @Mock private StrategyFactory<EmaMacdParameters> mockEmaMacdFactory;

  @Bind private ImmutableList<StrategyFactory<?>> strategyFactories;

  @Inject
  private StrategyManagerImpl strategyManager;

  private Strategy mockStrategy;
  private BarSeries barSeries;

  @Before
  public void setUp() {
    MockitoAnnotations.openMocks(this);

    // Configure mock factories
    when(mockSmaRsiFactory.getStrategyType()).thenReturn(StrategyType.SMA_RSI);
    when(mockEmaMacdFactory.getStrategyType()).thenReturn(StrategyType.EMA_MACD);

    // Initialize strategy factories field with mocked dependencies
    strategyFactories = ImmutableList.of(mockSmaRsiFactory, mockEmaMacdFactory);

    Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);

    // Create mock strategy and bar series for testing
    mockStrategy = mock(Strategy.class);
    barSeries = new BaseBarSeries();
  }

  @Test
  public void createStrategy_withValidSmaRsiParameters_returnsStrategy()
      throws InvalidProtocolBufferException {
    // Arrange
    SmaRsiParameters params =
        SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod(14)
            .setRsiPeriod(14)
            .setOverboughtThreshold(70)
            .setOversoldThreshold(30)
            .build();
    Any packedParams = Any.pack(params);

    when(mockSmaRsiFactory.createStrategy(barSeries, packedParams)).thenReturn(mockStrategy);

    // Act
    Strategy result =
        strategyManager.createStrategy(barSeries, StrategyType.SMA_RSI, packedParams);

    // Assert
    assertThat(result).isSameInstanceAs(mockStrategy);
  }

  @Test
  public void createStrategy_withValidEmaMacdParameters_returnsStrategy()
      throws InvalidProtocolBufferException {
    // Arrange
    EmaMacdParameters params =
        EmaMacdParameters.newBuilder()
            .setShortEmaPeriod(12)
            .setLongEmaPeriod(26)
            .setSignalPeriod(9)
            .build();
    Any packedParams = Any.pack(params);

    when(mockEmaMacdFactory.createStrategy(barSeries, packedParams)).thenReturn(mockStrategy);

    // Act
    Strategy result =
        strategyManager.createStrategy(barSeries, StrategyType.EMA_MACD, packedParams);

    // Assert
    assertThat(result).isSameInstanceAs(mockStrategy);
  }

  @Test
  public void createStrategy_withUnsupportedStrategyType_throwsIllegalArgumentException() {
    // Arrange
    SmaRsiParameters params =
        SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod(14)
            .setRsiPeriod(14)
            .setOverboughtThreshold(70)
            .setOversoldThreshold(30)
            .build();
    Any packedParams = Any.pack(params);

    // Act & Assert
    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class,
            () ->
                strategyManager.createStrategy(
                        barSeries, StrategyType.ADX_STOCHASTIC, packedParams));

    assertThat(thrown).hasMessageThat().contains("Unsupported strategy type: ADX_STOCHASTIC");
  }

  @Test
  public void createStrategy_whenFactoryThrowsException_propagatesException()
      throws InvalidProtocolBufferException {
    // Arrange
    SmaRsiParameters params =
        SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod(14)
            .setRsiPeriod(14)
            .setOverboughtThreshold(70)
            .setOversoldThreshold(30)
            .build();
    Any packedParams = Any.pack(params);

    InvalidProtocolBufferException expectedException = new InvalidProtocolBufferException("Test exception");
    when(mockSmaRsiFactory.createStrategy(barSeries, packedParams)).thenThrow(expectedException);

    // Act & Assert
    InvalidProtocolBufferException thrown =
        assertThrows(
            InvalidProtocolBufferException.class,
            () -> strategyManager.createStrategy(barSeries, StrategyType.SMA_RSI, packedParams));

    assertThat(thrown).isSameInstanceAs(expectedException);
  }

  @Test
  public void getStrategyTypes_returnsExpectedStrategyTypes()
      throws InvalidProtocolBufferException {
    // Arrange
    ImmutableList<StrategyType> expected = ImmutableList.of(StrategyType.EMA_MACD, StrategyType.SMA_RSI);

    // Act
    ImmutableList<StrategyType> actual = strategyManager.getStrategyTypes();

    // Assert
    assertThat(actual).containsExactlyElementsIn(expected);
  }
}
