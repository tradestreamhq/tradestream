package com.verlumen.tradestream.strategies.momentumoscillators;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.SmaRsiParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.RSIIndicator;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;

@RunWith(JUnit4.class)
public class SmaRsiStrategyFactoryTest {

    private static final int RSI_PERIOD = 14;
    private static final int MOVING_AVERAGE_PERIOD = 7;
    private static final double OVERBOUGHT_THRESHOLD = 70;
    private static final double OVERSOLD_THRESHOLD = 30;

    private SmaRsiStrategyFactory factory;
    private SmaRsiParameters params;
    private BaseBarSeries series;
    private Strategy strategy;

    // For debugging RSI and SMA calculations
    private RSIIndicator rsiIndicator;
    private SMAIndicator smaIndicator;
    private ClosePriceIndicator closePrice;

    @Before
    public void setUp() throws InvalidProtocolBufferException {
        factory = SmaRsiStrategyFactory.create();

        // Standard parameters
        params = SmaRsiParameters.newBuilder()
            .setRsiPeriod(RSI_PERIOD)
            .setMovingAveragePeriod(MOVING_AVERAGE_PERIOD)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();

        // Initialize series
        series = new BaseBarSeries();
        ZonedDateTime now = ZonedDateTime.now();

        // Bars 0..6: descending prices (50 -> 44)
        double price = 50.0;
        for (int i = 0; i < 7; i++) {
            series.addBar(createBar(now.plusMinutes(i), price));
            price -= 1.0;
        }

        // Bars 7..10: strong downward movement (20 -> 15 -> 10 -> 5)
        series.addBar(createBar(now.plusMinutes(7), 20.0));
        series.addBar(createBar(now.plusMinutes(8), 15.0));
        series.addBar(createBar(now.plusMinutes(9), 10.0));
        series.addBar(createBar(now.plusMinutes(10), 5.0));

        // Bars 11..13: strong upward movement (80 -> 85 -> 90)
        series.addBar(createBar(now.plusMinutes(11), 80.0));
        series.addBar(createBar(now.plusMinutes(12), 85.0));
        series.addBar(createBar(now.plusMinutes(13), 90.0));

        // Bars 14..20: keep RSI above 70 *consecutively* 
        for (int i = 14; i <= 20; i++) {
            series.addBar(createBar(now.plusMinutes(i), 90.0));
        }

        // Indicators
        closePrice = new ClosePriceIndicator(series);
        rsiIndicator = new RSIIndicator(closePrice, RSI_PERIOD);
        smaIndicator = new SMAIndicator(rsiIndicator, MOVING_AVERAGE_PERIOD);

        // Create strategy
        strategy = factory.createStrategy(series, params);
    }

    @Test
    public void getStrategyType_returnsSmaRsi() {
        assertThat(factory.getStrategyType()).isEqualTo(StrategyType.SMA_RSI);
    }

    @Test
    public void entryRule_shouldTrigger_whenRsiAndSmaAreUnderOversold() {
        for (int i = 6; i <= 10; i++) {
            System.out.printf(
                "Bar %d - Price: %.2f, RSI: %.2f, SMA: %.2f%n",
                i,
                closePrice.getValue(i).doubleValue(),
                rsiIndicator.getValue(i).doubleValue(),
                smaIndicator.getValue(i).doubleValue()
            );
        }

        // Expect entry by bar 7
        assertThat(strategy.getEntryRule().isSatisfied(7)).isTrue();
    }

    @Test
    public void exitRule_shouldTrigger_whenRsiAndSmaAreOverOverbought() {
        // Debug logs for bars 10..20
        for (int i = 10; i <= 20; i++) {
            double rsi = rsiIndicator.getValue(i).doubleValue();
            double sma = smaIndicator.getValue(i).doubleValue();
            System.out.printf(
                "Bar %d - Price: %.2f, RSI: %.2f, SMA: %.2f%n",
                i,
                closePrice.getValue(i).doubleValue(),
                rsi,
                sma
            );
        }

        // The rule is Over(RSI,70).and(Over(SMA(RSI),70)).
        // We check from bar 10 up to bar 20 to see when it first triggers.
        int exitIndex = -1;
        for (int i = 10; i <= 20; i++) {
            if (strategy.getExitRule().isSatisfied(i)) {
                exitIndex = i;
                break;
            }
        }

        System.out.println("Exit rule first satisfied at bar " + exitIndex);
        assertThat(exitIndex).isGreaterThan(0);
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateMovingAveragePeriod() throws InvalidProtocolBufferException {
        params = SmaRsiParameters.newBuilder()
            .setRsiPeriod(RSI_PERIOD)
            .setMovingAveragePeriod(-1)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();
        factory.createStrategy(series, params);
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateRsiPeriod() throws InvalidProtocolBufferException {
        params = SmaRsiParameters.newBuilder()
            .setRsiPeriod(-1)
            .setMovingAveragePeriod(MOVING_AVERAGE_PERIOD)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();
        factory.createStrategy(series, params);
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateOverboughtThreshold() throws InvalidProtocolBufferException {
        params = SmaRsiParameters.newBuilder()
            .setRsiPeriod(RSI_PERIOD)
            .setMovingAveragePeriod(MOVING_AVERAGE_PERIOD)
            .setOverboughtThreshold(-1)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();
        factory.createStrategy(series, params);
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateOversoldThreshold() throws InvalidProtocolBufferException {
        params = SmaRsiParameters.newBuilder()
            .setRsiPeriod(RSI_PERIOD)
            .setMovingAveragePeriod(MOVING_AVERAGE_PERIOD)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(-1)
            .build();
        factory.createStrategy(series, params);
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateThresholdOrdering() throws InvalidProtocolBufferException {
        params = SmaRsiParameters.newBuilder()
            .setRsiPeriod(RSI_PERIOD)
            .setMovingAveragePeriod(MOVING_AVERAGE_PERIOD)
            .setOverboughtThreshold(OVERSOLD_THRESHOLD)
            .setOversoldThreshold(OVERBOUGHT_THRESHOLD)
            .build();
        factory.createStrategy(series, params);
    }

    private BaseBar createBar(ZonedDateTime time, double price) {
        return new BaseBar(
            Duration.ofMinutes(1),
            time,
            price, // open
            price, // high
            price, // low
            price, // close
            100.0  // volume
        );
    }
}
