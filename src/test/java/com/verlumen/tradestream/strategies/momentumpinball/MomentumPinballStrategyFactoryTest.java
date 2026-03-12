package com.verlumen.tradestream.strategies.momentumpinball;

import static org.junit.Assert.assertNotNull;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import org.ta4j.core.num.DecimalNum;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;

/** Tests for {@link MomentumPinballStrategyFactory}. */
public class MomentumPinballStrategyFactoryTest {

  private final MomentumPinballStrategyFactory factory = new MomentumPinballStrategyFactory();

  @Test
  public void testCreateStrategyWithCustomParameters() throws InvalidProtocolBufferException {
    BarSeries barSeries = createTestBarSeries();

    var params =
        com.verlumen.tradestream.strategies.MomentumPinballParameters.newBuilder()
            .setShortPeriod(5)
            .setLongPeriod(15)
            .build();

    Any packedParams = Any.pack(params);
    Strategy strategy = factory.createStrategy(barSeries, params);

    assertNotNull(strategy);
    assertNotNull(strategy.getEntryRule());
    assertNotNull(strategy.getExitRule());
  }

  private BarSeries createTestBarSeries() {
    BarSeries barSeries = new BaseBarSeriesBuilder().build();
    ZonedDateTime now = ZonedDateTime.now();

    // Add some test bars
    for (int i = 0; i < 30; i++) {
      double price = 100.0 + i * 0.5;
      Duration duration = Duration.ofMinutes(1);
      Instant endTime = now.plusMinutes(i).toInstant();
      Instant beginTime = endTime.minus(duration);
      barSeries.addBar(
          new BaseBar(
              duration,
              beginTime,
              endTime,
              DecimalNum.valueOf(price),
              DecimalNum.valueOf(price + 1.0),
              DecimalNum.valueOf(price - 0.5),
              DecimalNum.valueOf(price + 0.2),
              DecimalNum.valueOf(1000.0),
              DecimalNum.valueOf(0),
              0));
    }

    return barSeries;
  }
}
