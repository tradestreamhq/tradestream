package com.verlumen.tradestream.strategies.volumeweightedmacd;

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

/** Tests for {@link VolumeWeightedMacdStrategyFactory}. */
public class VolumeWeightedMacdStrategyFactoryTest {

  private final VolumeWeightedMacdStrategyFactory factory = new VolumeWeightedMacdStrategyFactory();

  @Test
  public void testCreateStrategyWithCustomParameters() throws InvalidProtocolBufferException {
    var params =
        com.verlumen.tradestream.strategies.VolumeWeightedMacdParameters.newBuilder()
            .setShortPeriod(8)
            .setLongPeriod(21)
            .setSignalPeriod(5)
            .build();

    BarSeries barSeries = createTestBarSeries();
    Any packedParams = Any.pack(params);
    Strategy strategy = factory.createStrategy(barSeries, packedParams);

    assertNotNull(strategy);
    assertNotNull(strategy.getEntryRule());
    assertNotNull(strategy.getExitRule());
  }

  private BarSeries createTestBarSeries() {
    var barSeries = new BaseBarSeriesBuilder().build();
    var now = ZonedDateTime.now();

    for (int i = 0; i < 50; i++) {
      Duration duration = Duration.ofMinutes(1);
      Instant endTime = now.plusMinutes(i).toInstant();
      Instant beginTime = endTime.minus(duration);
      var bar =
          new BaseBar(
              duration,
              beginTime,
              endTime,
              DecimalNum.valueOf(100.0 + i),
              DecimalNum.valueOf(100.0 + i + 1),
              DecimalNum.valueOf(100.0 + i - 0.5),
              DecimalNum.valueOf(100.0 + i + 0.5),
              DecimalNum.valueOf(1000 + i * 10),
              DecimalNum.valueOf(0),
              0);
      barSeries.addBar(bar);
    }

    return barSeries;
  }
}
