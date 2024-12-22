package com.verlumen.tradestream.strategies.oscillators;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

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
        factory = new SmaRsiStrategyFactory();

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

        // Strong downward movement (bars 7..10)
        series.addBar(createBar(now.plusMinutes(7), 20.0));
        series.addBar(createBar(now.plusMinutes(8), 15.0));
        series.addBar(createBar(now.plusMinutes(9), 10.0));
        series.addBar(createBar(now.plusMinutes(10), 5.0));

        // Strong upward movement (bars 11..13)
        series.addBar(createBar(now.plusMinutes(11), 80.0));
        series.addBar(createBar(now.plusMinutes(12), 85.0));
        series.addBar(createBar(now.plusMinutes(13), 90.0));

        // Bars 14..20: keep RSI above 70 *consecutively* so that
        // the 7-bar SMA of RSI also climbs above 70 eventually.
        for (int i = 14; i <= 20; i++) {
            series.addBar(createBar(now.plusMinutes(i), 90.0));
        }

        // Initialize indicators
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
        // Log RSI and SMA values around bars 6..10
        for (int i = 6; i <= 10; i++) {
            System.out.printf(
                "Bar %d - Price: %.2f, RSI: %.2f, SMA: %.2f%n",
                i,
                closePrice.getValue(i).doubleValue(),
                rsiIndicator.getValue(i).doubleValue(),
                smaIndicator.getValue(i).doubleValue()
            );
        }

        // We expect the entry signal by bar 7, because RSI & SMA remain very low
        assertTrue(
            "Entry rule should trigger when RSI and SMA are below oversold at bar 7",
            strategy.getEntryRule().isSatisfied(7)
        );
    }

    @Test
    public void exitRule_shouldTrigger_whenRsiAndSmaAreOverOverbought() {
        // Log RSI and SMA values around bars 10..13
        for (int i = 10; i <= 13; i++) {
            System.out.printf(
                "Bar %d - Price: %.2f, RSI: %.2f, SMA: %.2f%n",
                i,
                closePrice.getValue(i).doubleValue(),
                rsiIndicator.getValue(i).doubleValue(),
                smaIndicator.getValue(i).doubleValue()
            );
        }

        // Not overbought at bar 10 (RSI=0)
        assertFalse("Should not trigger exit at bar 10", strategy.getExitRule().isSatisfied(10));

        // RSI crosses above 70 around bar 12, so the rule triggers at bar 12
        assertTrue(
           "Exit rule should trigger when RSI and SMA are above overbought at bar 12",
           strategy.getExitRule().isSatisfied(12)
        );
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

    /**
     * Helper for creating a Bar with a specific close price.
     */
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
