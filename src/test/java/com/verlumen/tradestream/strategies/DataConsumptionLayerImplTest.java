package com.verlumen.tradestream.strategies;

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

/**
 * Tests specific to the CandleWindow functionality
 */
@RunWith(JUnit4.class)
public class CandleWindowTest {
    private static final String CURRENCY_PAIR = "BTC/USD";
    private static final Duration TIMEFRAME = Duration.ofMinutes(1);
    private CandleWindow window;

    @Before
    public void setUp() {
        window = new CandleWindow(TIMEFRAME);
    }

    @Test
    public void addCandle_maintainsChronologicalOrder() {
        // Arrange
        Candle candle1 = createTestCandle(1000L);
        Candle candle2 = createTestCandle(2000L);
        Candle candle3 = createTestCandle(3000L);

        // Act
        window.addCandle(candle2);
        window.addCandle(candle1);
        window.addCandle(candle3);

        List<Candle> candles = window.getCandles(3);

        // Assert
        assertThat(candles).hasSize(3);
        assertThat(candles.get(0).getTimestamp()).isEqualTo(1000L);
        assertThat(candles.get(1).getTimestamp()).isEqualTo(2000L);
        assertThat(candles.get(2).getTimestamp()).isEqualTo(3000L);
    }

    private static Candle createTestCandle(long timestamp) {
        return Candle.newBuilder()
            .setTimestamp(timestamp)
            .setCurrencyPair(CURRENCY_PAIR)
            .build();
    }
}

/**
 * Tests specific to timeframe aggregation functionality
 */
@RunWith(JUnit4.class)
public class TimeframeAggregationTest {
    private static final String CURRENCY_PAIR = "BTC/USD";
    private static final Duration BASE_TIMEFRAME = Duration.ofMinutes(1);
    private static final Duration TIMEFRAME_5M = Duration.ofMinutes(5);

    private DataConsumptionLayerImpl dataConsumption;

    @Before
    public void setUp() {
        DataConsumptionLayer.Config config = DataConsumptionLayerImpl.ConfigImpl.create(
            "test-topic",
            "localhost:9092",
            ImmutableList.of(BASE_TIMEFRAME, TIMEFRAME_5M),
            BASE_TIMEFRAME
        );
        dataConsumption = new DataConsumptionLayerImpl(config);
    }

    @Test
    public void timeframeAggregation_aggregatesFiveOneMinuteCandles() {
        // Arrange
        long baseTime = 300000L; // 5-minute mark
        Candle[] oneMinCandles = new Candle[5];
        
        for (int i = 0; i < 5; i++) {
            oneMinCandles[i] = Candle.newBuilder()
                .setTimestamp(baseTime + (i * 60000))
                .setCurrencyPair(CURRENCY_PAIR)
                .setOpen(100.0 + i)
                .setHigh(101.0 + i)
                .setLow(99.0 + i)
                .setClose(100.5 + i)
                .setVolume(10.0)
                .build();
        }

        // Act
        for (Candle candle : oneMinCandles) {
            dataConsumption.consumeCandle(candle);
        }

        List<Candle> fiveMinCandles = dataConsumption.getCandlesForTimeframe(
            TIMEFRAME_5M, 1, CURRENCY_PAIR);

        // Assert
        assertThat(fiveMinCandles).hasSize(1);
        Candle aggregated = fiveMinCandles.get(0);
        assertThat(aggregated.getOpen()).isEqualTo(100.0);  // First candle's open
        assertThat(aggregated.getHigh()).isEqualTo(105.0);  // Highest high
        assertThat(aggregated.getLow()).isEqualTo(99.0);    // Lowest low
        assertThat(aggregated.getClose()).isEqualTo(104.5); // Last candle's close
        assertThat(aggregated.getVolume()).isEqualTo(50.0); // Sum of volumes
    }
}
