package com.verlumen.tradestream.strategies;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
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
import org.ta4j.core.Strategy;

@RunWith(JUnit4.class)
public class StrategyManagerImplTest {

    @Bind
    @Mock
    private StrategyFactory<SmaRsiParameters> mockSmaRsiFactory;

    @Bind
    @Mock 
    private StrategyFactory<EmaMacdParameters> mockEmaMacdFactory;

    private StrategyManagerImpl strategyManager;
    private Strategy mockStrategy;

    @Before
    public void setUp() {
        MockitoAnnotations.openMocks(this);

        // Configure mock factories
        when(mockSmaRsiFactory.getStrategyType()).thenReturn(StrategyType.SMA_RSI);
        when(mockEmaMacdFactory.getStrategyType()).thenReturn(StrategyType.EMA_MACD);

        // Create config with mock factories
        StrategyManagerImpl.Config config = StrategyManagerImpl.Config.create(
            ImmutableList.of(mockSmaRsiFactory, mockEmaMacdFactory));

        // Initialize strategy manager with mocked dependencies
        strategyManager = Guice.createInjector(BoundFieldModule.of(this))
            .getInstance(StrategyManagerImpl.class);

        // Create mock strategy for testing
        mockStrategy = mock(Strategy.class);
    }

    @Test
    public void createStrategy_withValidSmaRsiParameters_returnsStrategy() 
        throws InvalidProtocolBufferException {
        // Arrange
        SmaRsiParameters params = SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod(14)
            .setRsiPeriod(14)
            .setOverboughtThreshold(70)
            .setOversoldThreshold(30)
            .build();
        Any packedParams = Any.pack(params);

        when(mockSmaRsiFactory.createStrategy(packedParams)).thenReturn(mockStrategy);

        // Act
        Strategy result = strategyManager.createStrategy(StrategyType.SMA_RSI, packedParams);

        // Assert
        assertThat(result).isSameInstanceAs(mockStrategy);
    }

    @Test
    public void createStrategy_withValidEmaMacdParameters_returnsStrategy() 
        throws InvalidProtocolBufferException {
        // Arrange
        EmaMacdParameters params = EmaMacdParameters.newBuilder()
            .setShortEmaPeriod(12)
            .setLongEmaPeriod(26)
            .setSignalPeriod(9)
            .build();
        Any packedParams = Any.pack(params);

        when(mockEmaMacdFactory.createStrategy(packedParams)).thenReturn(mockStrategy);

        // Act
        Strategy result = strategyManager.createStrategy(StrategyType.EMA_MACD, packedParams);

        // Assert
        assertThat(result).isSameInstanceAs(mockStrategy);
    }

    @Test
    public void createStrategy_withUnsupportedStrategyType_throwsIllegalArgumentException() {
        // Arrange
        SmaRsiParameters params = SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod(14)
            .setRsiPeriod(14)
            .setOverboughtThreshold(70)
            .setOversoldThreshold(30)
            .build();
        Any packedParams = Any.pack(params);

        // Act & Assert
        IllegalArgumentException thrown = assertThrows(
            IllegalArgumentException.class,
            () -> strategyManager.createStrategy(StrategyType.ADX_STOCHASTIC, packedParams));
        
        assertThat(thrown).hasMessageThat()
            .contains("Unsupported strategy type: ADX_STOCHASTIC");
    }

    @Test
    public void createStrategy_whenFactoryThrowsException_propagatesException() 
        throws InvalidProtocolBufferException {
        // Arrange
        SmaRsiParameters params = SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod(14)
            .setRsiPeriod(14)
            .setOverboughtThreshold(70)
            .setOversoldThreshold(30)
            .build();
        Any packedParams = Any.pack(params);

        InvalidProtocolBufferException expectedException = 
            new InvalidProtocolBufferException("Test exception");
        when(mockSmaRsiFactory.createStrategy(packedParams))
            .thenThrow(expectedException);

        // Act & Assert
        InvalidProtocolBufferException thrown = assertThrows(
            InvalidProtocolBufferException.class,
            () -> strategyManager.createStrategy(StrategyType.SMA_RSI, packedParams));
        
        assertThat(thrown).isSameInstanceAs(expectedException);
    }
}
