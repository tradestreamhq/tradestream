package com.verlumen.tradestream.strategies.ichimokucloud;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.IchimokuCloudParameters;
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
public class IchimokuCloudStrategyFactoryTest {
  private IchimokuCloudStrategyFactory factory;
  private IchimokuCloudParameters params;
  private BaseBarSeries series;

  @Before
  public void setUp() {
    factory = new IchimokuCloudStrategyFactory();
    params =
        IchimokuCloudParameters.newBuilder()
            .setTenkanSenPeriod(9)
            .setKijunSenPeriod(26)
            .setSenkouSpanBPeriod(52)
            .setChikouSpanPeriod(26)
            .build();

    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 60; i++) {
      double price = 100 + 10 * Math.sin(i * 0.1);
      series.addBar(createBar(now.plusMinutes(i), price));
    }
  }

  @Test
  public void createStrategy_returnsValidStrategy() throws Exception {
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).contains("ICHIMOKU_CLOUD");
  }

  @Test(expected = IllegalArgumentException.class)
  public void createStrategy_invalidParams_throwsException() {
    IchimokuCloudParameters badParams =
        IchimokuCloudParameters.newBuilder()
            .setTenkanSenPeriod(0)
            .setKijunSenPeriod(0)
            .setSenkouSpanBPeriod(0)
            .setChikouSpanPeriod(0)
            .build();
    factory.createStrategy(series, badParams);
  }

  private BaseBar createBar(ZonedDateTime time, double price) {
    return new BaseBar(Duration.ofMinutes(1), time, price, price, price, price, 100.0);
  }
}
