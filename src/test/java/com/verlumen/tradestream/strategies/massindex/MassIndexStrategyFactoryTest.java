package com.verlumen.tradestream.strategies.massindex;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.MassIndexParameters;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.Bar;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;

import java.time.ZonedDateTime;
import java.time.ZoneId;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

public final class MassIndexStrategyFactoryTest {

    private MassIndexStrategyFactory factory;
    private BarSeries barSeries;

    @Before
    public void setUp() {
        factory = new MassIndexStrategyFactory();
        
        // Create a simple bar series for testing
        List<Bar> bars = new ArrayList<>();
        ZonedDateTime now = ZonedDateTime.now(ZoneId.of("UTC"));
        for (int i = 0; i < 50; i++) {
            bars.add(new BaseBar(
                Duration.ofMinutes(1),
                now.plusMinutes(i),
                100.0 + i * 0.1,  // open
                100.5 + i * 0.1,  // high
                99.5 + i * 0.1,   // low
                100.2 + i * 0.1,  // close
                1000.0 + i * 10   // volume
            ));
        }
        barSeries = new BaseBarSeries(bars);
    }

    @Test
    public void createStrategy_withDefaultParameters_returnsStrategy() {
        MassIndexParameters params = factory.getDefaultParameters();
        Strategy strategy = factory.createStrategy(barSeries, params);
        assertThat(strategy).isNotNull();
    }
}
