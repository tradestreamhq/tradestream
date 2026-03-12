package com.verlumen.tradestream.strategies.parabolicsarr;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.ParabolicSarParameters;
import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;
import org.ta4j.core.num.DecimalNum;

@RunWith(JUnit4.class)
public class ParabolicSarStrategyFactoryTest {
  private ParabolicSarStrategyFactory factory;
  private ParabolicSarParameters params;
  private BaseBarSeries series;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new ParabolicSarStrategyFactory();
    params =
        ParabolicSarParameters.newBuilder()
            .setAccelerationFactorStart(0.02)
            .setAccelerationFactorIncrement(0.02)
            .setAccelerationFactorMax(0.2)
            .build();

    series = new BaseBarSeriesBuilder().build();
    ZonedDateTime now = ZonedDateTime.now();

    // Create test data
    for (int i = 0; i < 50; i++) {
      double price = 100 + 10 * Math.sin(i * 0.1);
      series.addBar(createBar(now.plusMinutes(i), price));
    }
  }

  @Test
  public void createStrategy_returnsValidStrategy() throws InvalidProtocolBufferException {
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).contains("PARABOLIC_SAR");
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateAccelerationFactorStart() throws InvalidProtocolBufferException {
    params =
        ParabolicSarParameters.newBuilder()
            .setAccelerationFactorStart(-0.01)
            .setAccelerationFactorIncrement(0.02)
            .setAccelerationFactorMax(0.2)
            .build();
    factory.createStrategy(series, params);
  }

  private BaseBar createBar(ZonedDateTime time, double price) {
    Duration duration = Duration.ofMinutes(1);
    Instant endTime = time.toInstant();
    Instant beginTime = endTime.minus(duration);
    return new BaseBar(
        duration,
        beginTime,
        endTime,
        DecimalNum.valueOf(price),
        DecimalNum.valueOf(price),
        DecimalNum.valueOf(price),
        DecimalNum.valueOf(price),
        DecimalNum.valueOf(100.0),
        DecimalNum.valueOf(0),
        0);
  }
}
