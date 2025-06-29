package com.verlumen.tradestream.strategies.volumeweightedmacd;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyType;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

/** Tests for {@link VolumeWeightedMacdStrategyFactory}. */
public class VolumeWeightedMacdStrategyFactoryTest {

  private final VolumeWeightedMacdStrategyFactory factory = new VolumeWeightedMacdStrategyFactory();

  @Test
  public void testGetStrategyType() {
    assertEquals(StrategyType.VOLUME_WEIGHTED_MACD, factory.getStrategyType());
  }

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
    var barSeries = new BaseBarSeries();
    var now = ZonedDateTime.now();

    for (int i = 0; i < 50; i++) {
      var bar =
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              100.0 + i,
              100.0 + i + 1,
              100.0 + i - 0.5,
              100.0 + i + 0.5,
              1000 + i * 10);
      barSeries.addBar(bar);
    }

    return barSeries;
  }
}
