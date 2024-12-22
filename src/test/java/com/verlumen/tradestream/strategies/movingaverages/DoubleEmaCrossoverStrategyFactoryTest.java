package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
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

@RunWith(JUnit4.class)
public class DoubleEmaCrossoverStrategyFactoryTest {
    private static final int SHORT_EMA = 3;
    private static final int LONG_EMA = 7;

    @Inject 
    private DoubleEmaCrossoverStrategyFactory factory;

    private DoubleEmaCrossoverParameters params;
    private BaseBarSeries series;
    private Strategy strategy;

    @Before
    public void setUp() {
        Guice.createInjector().injectMembers(this);
        
        // Create standard parameters
        params = DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setLongEmaPeriod(LONG_EMA)
            .build();

        // Initialize series
        series = new BaseBarSeries();
        ZonedDateTime now = ZonedDateTime.now();

        // Add bars that will create a clear crossover pattern
        // First establish baseline with steady prices
        for (int i = 0; i < 7; i++) {
            series.addBar(createBar(now.plusMinutes(i), 50.0));
        }
        
        // Create crossover scenario
        series.addBar(createBar(now.plusMinutes(7), 60.0));  // Price starts rising
        series.addBar(createBar(now.plusMinutes(8), 70.0));  // Continues up
        series.addBar(createBar(now.plusMinutes(9), 75.0));  // Peaks
        series.addBar(createBar(now.plusMinutes(10), 45.0)); // Sharp drop
        series.addBar(createBar(now.plusMinutes(11), 40.0)); // Continues down
        series.addBar(createBar(now.plusMinutes(12), 35.0)); // Establishes downtrend

        strategy = factory.createStrategy(series, params);
    }

    @Test
    public void getStrategyType_returnsDoubleEmaCrossover() {
        assertThat(factory.getStrategyType()).isEqualTo(StrategyType.DOUBLE_EMA_CROSSOVER);
    }

    @Test
    public void entryRule_shouldTrigger_whenShortEmaCrossesAboveLongEma() {
        // No entry signal during baseline period
        assertFalse(strategy.getEntryRule().isSatisfied(6));
        
        // Should detect entry around when short EMA crosses above long EMA
        assertTrue("Entry rule should trigger when short EMA crosses above long EMA",
            strategy.getEntryRule().isSatisfied(8));
    }

    @Test
    public void exitRule_shouldTrigger_whenShortEmaCrossesBelowLongEma() {
        // No exit signal during uptrend
        assertFalse(strategy.getExitRule().isSatisfied(9));
        
        // Should detect exit around when short EMA crosses below long EMA
        assertTrue("Exit rule should trigger when short EMA crosses below long EMA",
            strategy.getExitRule().isSatisfied(11));
    }

    @Test(expected = IllegalArgumentException.class)
    public void constructor_shouldThrowException_whenShortEmaPeriodIsNegative() {
        params = DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(-1)
            .setLongEmaPeriod(LONG_EMA)
            .build();
        factory.createStrategy(series, params);
    }

    @Test(expected = IllegalArgumentException.class)
    public void constructor_shouldThrowException_whenLongEmaPeriodIsNegative() {
        params = DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setLongEmaPeriod(-1)
            .build();
        factory.createStrategy(series, params);
    }

    @Test(expected = IllegalArgumentException.class)
    public void constructor_shouldThrowException_whenLongEmaPeriodLessThanShortPeriod() {
        params = DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(LONG_EMA)
            .setLongEmaPeriod(SHORT_EMA)
            .build();
        factory.createStrategy(series, params);
    }

    private BaseBar createBar(ZonedDateTime time, double price) {
        return new BaseBar(
            Duration.ofMinutes(1),
            time,
            price, // Open
            price, // High
            price, // Low
            price, // Close
            100.0  // Volume
        );
    }
}
