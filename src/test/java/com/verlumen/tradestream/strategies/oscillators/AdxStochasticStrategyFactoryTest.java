package com.verlumen.tradestream.strategies.oscillators;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.AdxStochasticParameters;
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
import org.ta4j.core.indicators.adx.ADXIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.StochasticOscillatorKIndicator;

@RunWith(JUnit4.class)
public class AdxStochasticStrategyFactoryTest {
    private static final int ADX_PERIOD = 14;
    private static final int STOCHASTIC_K_PERIOD = 14;
    private static final int OVERBOUGHT_THRESHOLD = 80;
    private static final int OVERSOLD_THRESHOLD = 20;

    private AdxStochasticStrategyFactory factory;
    private AdxStochasticParameters params;
    private BaseBarSeries series;
    private Strategy strategy;

    // For debugging ADX and Stochastic K calculations
    private ADXIndicator adxIndicator;
    private StochasticOscillatorKIndicator stochasticK;
    private ClosePriceIndicator closePrice;

    @Before
    public void setUp() throws InvalidProtocolBufferException {
        factory = AdxStochasticStrategyFactory.create();

        // Standard parameters
        params = AdxStochasticParameters.newBuilder()
            .setAdxPeriod(ADX_PERIOD)
            .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();

        // Initialize series
        series = new BaseBarSeries();
        ZonedDateTime now = ZonedDateTime.now();

        // Create sample price data (for simplicity, we'll just use a sine wave pattern)
        for (int i = 0; i < 50; i++) {
            double price = 50 + 20 * Math.sin(i * 0.2);
            series.addBar(createBar(now.plusMinutes(i), price));
        }

        // Indicators
        closePrice = new ClosePriceIndicator(series);
        adxIndicator = new ADXIndicator(series, ADX_PERIOD);
        stochasticK = new StochasticOscillatorKIndicator(series, STOCHASTIC_K_PERIOD);

        // Create strategy
        strategy = factory.createStrategy(series, params);
    }

    @Test
    public void getStrategyType_returnsAdxStochastic() {
        assertThat(factory.getStrategyType()).isEqualTo(StrategyType.ADX_STOCHASTIC);
    }

    @Test
    public void entryRule_shouldTrigger_whenAdxAbove20AndStochasticKBelowOversold() {
        // Find a bar index where ADX is above 20 and Stochastic K is below oversold threshold
        int entryIndex = -1;
        for (int i = ADX_PERIOD; i < series.getBarCount(); i++) {
            if (adxIndicator.getValue(i).doubleValue() > 20
                && stochasticK.getValue(i).doubleValue() < params.getOversoldThreshold()) {
                entryIndex = i;
                break;
            }
        }

        // Log values for debugging
        if (entryIndex > 0) {
            System.out.printf(
                "Entry at Bar %d - Price: %.2f, ADX: %.2f, Stochastic K: %.2f%n",
                entryIndex,
                closePrice.getValue(entryIndex).doubleValue(),
                adxIndicator.getValue(entryIndex).doubleValue(),
                stochasticK.getValue(entryIndex).doubleValue()
            );
            assertThat(strategy.getEntryRule().isSatisfied(entryIndex)).isTrue();
        } else {
            System.out.println("No entry signal found with current data and parameters.");
        }
    }

    @Test
    public void exitRule_shouldTrigger_whenAdxBelow20AndStochasticKAboveOverbought() {
        // Find a bar index where ADX is below 20 and Stochastic K is above overbought threshold
        int exitIndex = -1;
        for (int i = ADX_PERIOD; i < series.getBarCount(); i++) {
            if (adxIndicator.getValue(i).doubleValue() < 20
                && stochasticK.getValue(i).doubleValue() > params.getOverboughtThreshold()) {
                exitIndex = i;
                break;
            }
        }

        // Log values for debugging
        if (exitIndex > 0) {
            System.out.printf(
                "Exit at Bar %d - Price: %.2f, ADX: %.2f, Stochastic K: %.2f%n",
                exitIndex,
                closePrice.getValue(exitIndex).doubleValue(),
                adxIndicator.getValue(exitIndex).doubleValue(),
                stochasticK.getValue(exitIndex).doubleValue()
            );
            assertThat(strategy.getExitRule().isSatisfied(exitIndex)).isTrue();
        } else {
            System.out.println("No exit signal found with current data and parameters.");
        }
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateAdxPeriod() throws InvalidProtocolBufferException {
        params = AdxStochasticParameters.newBuilder()
            .setAdxPeriod(-1)
            .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();
        factory.createStrategy(series, params);
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateStochasticKPeriod() throws InvalidProtocolBufferException {
        params = AdxStochasticParameters.newBuilder()
            .setAdxPeriod(ADX_PERIOD)
            .setStochasticKPeriod(-1)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();
        factory.createStrategy(series, params);
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateOverboughtThreshold() throws InvalidProtocolBufferException {
        params = AdxStochasticParameters.newBuilder()
            .setAdxPeriod(ADX_PERIOD)
            .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
            .setOverboughtThreshold(-1)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();
        factory.createStrategy(series, params);
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateOversoldThreshold() throws InvalidProtocolBufferException {
        params = AdxStochasticParameters.newBuilder()
            .setAdxPeriod(ADX_PERIOD)
            .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(-1)
            .build();
        factory.createStrategy(series, params);
    }

    @Test(expected = IllegalArgumentException.class)
    public void validateThresholdOrdering() throws InvalidProtocolBufferException {
        params = AdxStochasticParameters.newBuilder()
            .setAdxPeriod(ADX_PERIOD)
            .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
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
