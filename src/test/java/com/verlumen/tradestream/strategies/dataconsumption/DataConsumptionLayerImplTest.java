package com.verlumen.tradestream.strategies.dataconsumption;

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.Mockito.*;

import com.google.common.collect.ImmutableList;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.marketdata.Candle;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

import java.time.Duration;
import java.util.List;

@RunWith(JUnit4.class)
public class DataConsumptionLayerImplTest {
    @Rule public MockitoRule mockito = MockitoJUnit.rule();

    private static final String CURRENCY_PAIR = "BTC/USD";
    private static final Duration BASE_TIMEFRAME = Duration.ofMinutes(1);
    private static final Duration TIMEFRAME_5M = Duration.ofMinutes(5);
    private static final Duration TIMEFRAME_15M = Duration.ofMinutes(15);
    private static final ImmutableList<Duration> SUPPORTED_TIMEFRAMES = 
        ImmutableList.of(BASE_TIMEFRAME, TIMEFRAME_5M, TIMEFRAME_15M);

    @Mock private DataConsumptionLayer.Config mockConfig;
    private DataConsumptionLayerImpl dataConsumption;

    @Before
    public void setUp() {
        when(mockConfig.getKafkaTopic()).thenReturn("test-topic");
        when(mockConfig.getKafkaBootstrapServers()).thenReturn("localhost:9092");
        when(mockConfig.getSupportedTimeframes()).thenReturn(SUPPORTED_TIMEFRAMES);
        when(mockConfig.getBaseCandleTimeframe()).thenReturn(BASE_TIMEFRAME);

        dataConsumption = new DataConsumptionLayerImpl(mockConfig);
    }

    @Test
    public void consumeCandle_singleCandle_retrievableFromWindow() {
        // Arrange
        Candle candle = createTestCandle(1000L, 100.0, 101.0, 99.0, 100.5, 10.0);

        // Act
        dataConsumption.consumeCandle(candle);
        List<Candle> retrieved = dataConsumption.getCandlesForTimeframe(
            BASE_TIMEFRAME, 1, CURRENCY_PAIR);

        // Assert
        assertThat(retrieved).hasSize(1);
        assertThat(retrieved.get(0)).isEqualTo(candle);
    }

    @Test
    public void consumeCandle_multipleCandles_maintainsOrder() {
        // Arrange
        Candle candle1 = createTestCandle(1000L, 100.0, 101.0, 99.0, 100.5, 10.0);
        Candle candle2 = createTestCandle(2000L, 100.5, 102.0, 100.0, 101.5, 15.0);

        // Act
        dataConsumption.consumeCandle(candle1);
        dataConsumption.consumeCandle(candle2);
        List<Candle> retrieved = dataConsumption.getCandlesForTimeframe(
            BASE_TIMEFRAME, 2, CURRENCY_PAIR);

        // Assert
        assertThat(retrieved).hasSize(2);
        assertThat(retrieved.get(0)).isEqualTo(candle1);
        assertThat(retrieved.get(1)).isEqualTo(candle2);
    }

    @Test
    public void consumeCandle_windowSize_respectsLimit() {
        // Arrange
        Candle candle1 = createTestCandle(1000L, 100.0, 101.0, 99.0, 100.5, 10.0);
        Candle candle2 = createTestCandle(2000L, 100.5, 102.0, 100.0, 101.5, 15.0);
        Candle candle3 = createTestCandle(3000L, 101.5, 103.0, 101.0, 102.5, 20.0);

        // Act
        dataConsumption.consumeCandle(candle1);
        dataConsumption.consumeCandle(candle2);
        dataConsumption.consumeCandle(candle3);
        List<Candle> retrieved = dataConsumption.getCandlesForTimeframe(
            BASE_TIMEFRAME, 2, CURRENCY_PAIR);

        // Assert
        assertThat(retrieved).hasSize(2);
        assertThat(retrieved.get(0)).isEqualTo(candle2);
        assertThat(retrieved.get(1)).isEqualTo(candle3);
    }

    @Test
    public void getSupportedTimeframes_returnsConfiguredTimeframes() {
        // Act
        List<Duration> timeframes = dataConsumption.getSupportedTimeframes();

        // Assert
        assertThat(timeframes).containsExactlyElementsIn(SUPPORTED_TIMEFRAMES);
    }

    @Test
    public void getCandlesForTimeframe_unknownPair_returnsEmptyList() {
        // Act
        List<Candle> candles = dataConsumption.getCandlesForTimeframe(
            BASE_TIMEFRAME, 1, "UNKNOWN/PAIR");

        // Assert
        assertThat(candles).isEmpty();
    }

    @Test
    public void getCandlesForTimeframe_unsupportedTimeframe_returnsEmptyList() {
        // Arrange
        Candle candle = createTestCandle(1000L, 100.0, 101.0, 99.0, 100.5, 10.0);
        dataConsumption.consumeCandle(candle);

        // Act
        List<Candle> candles = dataConsumption.getCandlesForTimeframe(
            Duration.ofHours(1), 1, CURRENCY_PAIR);

        // Assert
        assertThat(candles).isEmpty();
    }

    private static Candle createTestCandle(
            long timestamp, 
            double open, 
            double high, 
            double low, 
            double close, 
            double volume) {
        return Candle.newBuilder()
            .setTimestamp(timestamp)
            .setCurrencyPair(CURRENCY_PAIR)
            .setOpen(open)
            .setHigh(high)
            .setLow(low)
            .setClose(close)
            .setVolume(volume)
            .build();
    }
}
