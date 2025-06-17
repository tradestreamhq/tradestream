package com.verlumen.tradestream.strategies.parabolicsarr;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.ParabolicSarParameters;
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

    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Create test data
    for (int i = 0; i < 50; i++) {
      double price = 100 + 10 * Math.sin(i * 0.1);
      series.addBar(createBar(now.plusMinutes(i), price));
    }
  }

  @Test
  public void getStrategyType_returnsParabolicSar() {
    assertThat(factory.getStrategyType()).isEqualTo(StrategyType.PARABOLIC_SAR);
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
    return new BaseBar(Duration.ofMinutes(1), time, price, price, price, price, 100.0);
  }
}
