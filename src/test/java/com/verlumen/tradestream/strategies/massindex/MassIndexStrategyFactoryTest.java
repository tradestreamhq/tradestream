package com.verlumen.tradestream.strategies.massindex;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.protos.strategies.MassIndexParameters;
import com.verlumen.tradestream.protos.strategies.Strategy;
import com.verlumen.tradestream.ta4j.TestBarSeriesBuilder;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.rules.AndRule;
import org.ta4j.core.rules.OrRule;

import java.time.ZonedDateTime;

public final class MassIndexStrategyFactoryTest {

    private MassIndexStrategyFactory factory;
    private BarSeries barSeries;

    @Before
    public void setUp() {
        factory = new MassIndexStrategyFactory();
        
        // Create a simple bar series for testing
        barSeries = TestBarSeriesBuilder.createBarSeries();
        ZonedDateTime now = ZonedDateTime.now();
        for (int i = 0; i < 50; i++) {
            barSeries.addBar(TestBarSeriesBuilder.createBar(
                now.plusMinutes(i),
                100.0 + i * 0.1,  // open
                100.5 + i * 0.1,  // high
                99.5 + i * 0.1,   // low
                100.2 + i * 0.1,  // close
                1000.0 + i * 10   // volume
            ));
        }
    }

    @Test
    public void createStrategy_returnsValidStrategy() throws InvalidProtocolBufferException {
        MassIndexParameters params = MassIndexParameters.newBuilder()
                .setEmaPeriod(25)
                .setSumPeriod(9)
                .build();

        Any packedParams = Any.pack(params);
        Strategy strategy = factory.createStrategy(barSeries, packedParams);

        assertThat(strategy).isNotNull();
        assertThat(strategy.getEntryRule()).isInstanceOfAny(AndRule.class, OrRule.class);
        assertThat(strategy.getExitRule()).isInstanceOfAny(AndRule.class, OrRule.class);
    }

    @Test(expected = InvalidProtocolBufferException.class)
    public void createStrategy_withInvalidParameters_throwsException() throws InvalidProtocolBufferException {
        Strategy invalidStrategy = Strategy.newBuilder()
                .setStrategyType(Strategy.StrategyType.RSI_EMA_CROSSOVER)
                .build();

        Any packedParams = Any.pack(invalidStrategy);
        factory.createStrategy(barSeries, packedParams);
    }

    @Test
    public void getStrategyType_returnsMassIndex() {
        assertThat(factory.getStrategyType()).isEqualTo(Strategy.StrategyType.MASS_INDEX);
    }
}
