package com.verlumen.tradestream.strategies.momentumpinball;

import static org.junit.Assert.assertNotNull;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
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
    BarSeries barSeries = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Add some test bars
    for (int i = 0; i < 30; i++) {
      double price = 100.0 + i * 0.5;
      barSeries.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              price,
              price + 1.0,
              price - 0.5,
              price + 0.2,
              1000.0));
    }

    return barSeries;
  }
}
