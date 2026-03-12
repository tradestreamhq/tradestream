package com.verlumen.tradestream.strategies.trixsignalline;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.TrixSignalLineParameters;
import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import org.ta4j.core.num.DecimalNum;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;

@RunWith(JUnit4.class)
public final class TrixSignalLineStrategyFactoryTest {

  private final TrixSignalLineStrategyFactory factory = new TrixSignalLineStrategyFactory();

  @Test
  public void getDefaultParameters_returnsValidParameters() {
    TrixSignalLineParameters params = factory.getDefaultParameters();

    assertThat(params.getTrixPeriod()).isEqualTo(15);
    assertThat(params.getSignalPeriod()).isEqualTo(9);
  }

  @Test
  public void createStrategy_withDefaultParameters_createsValidStrategy()
      throws InvalidProtocolBufferException {
    TrixSignalLineParameters params = factory.getDefaultParameters();
    BarSeries series = new BaseBarSeriesBuilder().build();

    // Add some test data
    ZonedDateTime now1 = ZonedDateTime.now();
    Duration duration1 = Duration.ofMinutes(1);
    Instant endTime1 = now1.toInstant();
    Instant beginTime1 = endTime1.minus(duration1);
    series.addBar(
        new BaseBar(duration1, beginTime1, endTime1,
            DecimalNum.valueOf(100.0), DecimalNum.valueOf(105.0),
            DecimalNum.valueOf(99.0), DecimalNum.valueOf(103.0),
            DecimalNum.valueOf(1000.0), DecimalNum.valueOf(0), 0));
    Instant endTime2 = now1.plusMinutes(1).toInstant();
    Instant beginTime2 = endTime2.minus(duration1);
    series.addBar(
        new BaseBar(duration1, beginTime2, endTime2,
            DecimalNum.valueOf(103.0), DecimalNum.valueOf(107.0),
            DecimalNum.valueOf(102.0), DecimalNum.valueOf(106.0),
            DecimalNum.valueOf(1200.0), DecimalNum.valueOf(0), 0));

    org.ta4j.core.Strategy strategy = factory.createStrategy(series, params);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }

  @Test
  public void createStrategy_withCustomParameters_createsValidStrategy()
      throws InvalidProtocolBufferException {
    TrixSignalLineParameters params =
        TrixSignalLineParameters.newBuilder().setTrixPeriod(20).setSignalPeriod(5).build();

    BarSeries series = new BaseBarSeriesBuilder().build();
    ZonedDateTime now2 = ZonedDateTime.now();
    Duration duration2 = Duration.ofMinutes(1);
    Instant endTime3 = now2.toInstant();
    Instant beginTime3 = endTime3.minus(duration2);
    series.addBar(
        new BaseBar(duration2, beginTime3, endTime3,
            DecimalNum.valueOf(100.0), DecimalNum.valueOf(105.0),
            DecimalNum.valueOf(99.0), DecimalNum.valueOf(103.0),
            DecimalNum.valueOf(1000.0), DecimalNum.valueOf(0), 0));

    org.ta4j.core.Strategy strategy = factory.createStrategy(series, params);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}
