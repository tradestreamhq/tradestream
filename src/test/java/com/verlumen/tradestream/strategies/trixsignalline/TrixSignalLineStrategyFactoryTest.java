package com.verlumen.tradestream.strategies.trixsignalline;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.TrixSignalLineParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;

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
    BarSeries series = new BaseBarSeries();

    // Add some test data
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), ZonedDateTime.now(), 100.0, 105.0, 99.0, 103.0, 1000.0));
    series.addBar(
        new BaseBar(
            Duration.ofMinutes(1),
            ZonedDateTime.now().plusMinutes(1),
            103.0,
            107.0,
            102.0,
            106.0,
            1200.0));

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

    BarSeries series = new BaseBarSeries();
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), ZonedDateTime.now(), 100.0, 105.0, 99.0, 103.0, 1000.0));

    org.ta4j.core.Strategy strategy = factory.createStrategy(series, params);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}
