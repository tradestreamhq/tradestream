package com.verlumen.tradestream.strategies.donchianbreakout;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DonchianBreakoutParameters;
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
public class DonchianBreakoutStrategyFactoryTest {
  private DonchianBreakoutStrategyFactory factory;
  private DonchianBreakoutParameters params;
  private BaseBarSeries series;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new DonchianBreakoutStrategyFactory();
    params = DonchianBreakoutParameters.newBuilder().setDonchianPeriod(20).build();

    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Create test data with breakout pattern
    for (int i = 0; i < 50; i++) {
      double price = 100 + (i > 25 ? 20 : 0); // Breakout after bar 25
      series.addBar(createBar(now.plusMinutes(i), price));
    }
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateDonchianPeriod() throws InvalidProtocolBufferException {
    params = DonchianBreakoutParameters.newBuilder().setDonchianPeriod(-1).build();
    factory.createStrategy(series, params);
  }

  private BaseBar createBar(ZonedDateTime time, double price) {
    return new BaseBar(Duration.ofMinutes(1), time, price, price, price, price, 100.0);
  }
}
