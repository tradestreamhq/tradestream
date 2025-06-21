package com.verlumen.tradestream.strategies.macdcrossover;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.MacdCrossoverParameters;
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
public class MacdCrossoverStrategyFactoryTest {
  private MacdCrossoverStrategyFactory factory;
  private MacdCrossoverParameters params;
  private BaseBarSeries series;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new MacdCrossoverStrategyFactory();
    params =
        MacdCrossoverParameters.newBuilder()
            .setShortEmaPeriod(12)
            .setLongEmaPeriod(26)
            .setSignalPeriod(9)
            .build();

    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Create test data
    for (int i = 0; i < 50; i++) {
      double price = 100 + 10 * Math.sin(i * 0.2);
      series.addBar(createBar(now.plusMinutes(i), price));
    }
  }

  @Test
  public void createStrategy_returnsValidStrategy() throws InvalidProtocolBufferException {
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).contains("MACD_CROSSOVER");
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateShortEmaPeriod() throws InvalidProtocolBufferException {
    params =
        MacdCrossoverParameters.newBuilder()
            .setShortEmaPeriod(-1)
            .setLongEmaPeriod(26)
            .setSignalPeriod(9)
            .build();
    factory.createStrategy(series, params);
  }

  private BaseBar createBar(ZonedDateTime time, double price) {
    return new BaseBar(Duration.ofMinutes(1), time, price, price, price, price, 100.0);
  }
}
