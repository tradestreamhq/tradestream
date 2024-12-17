package com.verlumen.tradestream.strategies.dataconsumption;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.marketdata.Candle;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

import java.time.Duration;
import java.util.List;

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
