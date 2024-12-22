package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
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
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;

@RunWith(JUnit4.class)
public class DoubleEmaCrossoverStrategyFactoryTest {
    private static final int SHORT_EMA = 3;
    private static final int LONG_EMA = 7;
    
    // For debugging EMA calculations
    private EMAIndicator shortEma;
    private EMAIndicator longEma;
    private ClosePriceIndicator closePrice;

    @Inject 
    private DoubleEmaCrossoverStrategyFactory factory;

    private DoubleEmaCrossoverParameters params;
    private BaseBarSeries series;
    private Strategy strategy;

    @Before
    public void setUp() throws InvalidProtocolBufferException {
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
        
        // Create stronger upward movement to force crossover
        series.addBar(createBar(now.plusMinutes(7), 65.0));   // Sharper rise
        series.addBar(createBar(now.plusMinutes(8), 80.0));   // Continues up strongly
        series.addBar(createBar(now.plusMinutes(9), 85.0));   // Maintains high level
        series.addBar(createBar(now.plusMinutes(10), 90.0));  // Still high
        
        // Create stronger downward movement
        series.addBar(createBar(now.plusMinutes(11), 40.0));  // Sharp drop
        series.addBar(createBar(now.plusMinutes(12), 30.0));  // Continues down strongly
        series.addBar(createBar(now.plusMinutes(13), 25.0));  // Further drop

        // Initialize indicators for debugging
        closePrice = new ClosePriceIndicator(series);
        shortEma = new EMAIndicator(closePrice, SHORT_EMA);
        longEma = new EMAIndicator(closePrice, LONG_EMA);

        strategy = factory.createStrategy(series, params);
    }

    @Test
    public void getStrategyType_returnsDoubleEmaCrossover() {
        assertThat(factory.getStrategyType()).isEqualTo(StrategyType.DOUBLE_EMA_CROSSOVER);
    }

    @Test
    public void entryRule_shouldTrigger_whenShortEmaCrossesAboveLongEma() {
        // Log EMA values around expected crossover point
        for (int i = 6; i <= 9; i++) {
            System.out.printf("Bar %d - Price: %.2f, Short EMA: %.2f, Long EMA: %.2f%n",
                i,
                closePrice.getValue(i).doubleValue(),
                shortEma.getValue(i).doubleValue(),
                longEma.getValue(i).doubleValue());
        }

        // No entry signal during baseline period
        assertFalse("Should not trigger entry during baseline",
            strategy.getEntryRule().isSatisfied(6));
        
        // Should detect entry when short EMA crosses above long EMA
        assertTrue("Entry rule should trigger when short EMA crosses above long EMA",
            strategy.getEntryRule().isSatisfied(8));
    }

    @Test
    public void exitRule_shouldTrigger_whenShortEmaCrossesBelowLongEma() {
        // Log EMA values around expected crossover point
        for (int i = 10; i <= 13; i++) {
            System.out.printf("Bar %d - Price: %.2f, Short EMA: %.2f, Long EMA: %.2f%n",
                i,
                closePrice.getValue(i).doubleValue(),
                shortEma.getValue(i).doubleValue(),
                longEma.getValue(i).doubleValue());
        }

        // No exit signal during uptrend
        assertFalse("Should not trigger exit during uptrend",
            strategy.getExitRule().isSatisfied(10));
        
        // Should detect exit when short EMA crosses below long EMA
        assertTrue("Exit rule should trigger when short EMA crosses below long EMA",
            strategy.getExitRule().isSatisfied(12));
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateShortEmaPeriod() throws InvalidProtocolBufferException {
        params = DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(-1)
            .setLongEmaPeriod(LONG_EMA)
            .build();
        factory.createStrategy(series, params);
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateLongEmaPeriod() throws InvalidProtocolBufferException {
        params = DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setLongEmaPeriod(-1)
            .build();
        factory.createStrategy(series, params);
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateEmaPeriodOrdering() throws InvalidProtocolBufferException {
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
