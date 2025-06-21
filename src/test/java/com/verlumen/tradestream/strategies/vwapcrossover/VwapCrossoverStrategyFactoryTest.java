package com.verlumen.tradestream.strategies.vwapcrossover;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.VwapCrossoverParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.volume.VWAPIndicator;

@RunWith(JUnit4.class)
public class VwapCrossoverStrategyFactoryTest {
  private static final int VWAP_PERIOD = 10;
  private static final int MA_PERIOD = 10;

  private VwapCrossoverStrategyFactory factory;
  private VwapCrossoverParameters params;
  private BaseBarSeries series;
  private Strategy strategy;

  // For debugging VWAP calculations
  private VWAPIndicator vwapIndicator;
  private SMAIndicator smaIndicator;
  private ClosePriceIndicator closePrice;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new VwapCrossoverStrategyFactory();

    // Standard parameters
    params =
        VwapCrossoverParameters.newBuilder()
            .setVwapPeriod(VWAP_PERIOD)
            .setMovingAveragePeriod(MA_PERIOD)
            .build();

    // Initialize series
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // ---------------------------------------------------------------------
    // 1) Baseline - price below VWAP
    // ---------------------------------------------------------------------
    double price = 50.0;
    double volume = 100.0;
    for (int i = 0; i < 7; i++) {
      series.addBar(createBar(now.plusMinutes(i), price, volume));
      price -= 1.0;
    }

    // ---------------------------------------------------------------------
    // 2) Strong upward movement - price crosses above VWAP
    // ---------------------------------------------------------------------
    series.addBar(createBar(now.plusMinutes(7), 65.0, 150.0));
    series.addBar(createBar(now.plusMinutes(8), 80.0, 200.0));
    series.addBar(createBar(now.plusMinutes(9), 85.0, 180.0));
    series.addBar(createBar(now.plusMinutes(10), 90.0, 160.0));

    // ---------------------------------------------------------------------
    // 3) Downward movement - price crosses below VWAP
    // ---------------------------------------------------------------------
    series.addBar(createBar(now.plusMinutes(11), 40.0, 120.0));
    series.addBar(createBar(now.plusMinutes(12), 30.0, 140.0));
    series.addBar(createBar(now.plusMinutes(13), 25.0, 110.0));

    // Initialize indicators for debugging
    closePrice = new ClosePriceIndicator(series);
    vwapIndicator = new VWAPIndicator(series, VWAP_PERIOD);
    smaIndicator = new SMAIndicator(closePrice, MA_PERIOD);

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void entryRule_shouldTrigger_whenPriceCrossesAboveVwap() {
    // Log VWAP and price values around the expected cross-up
    for (int i = 6; i <= 9; i++) {
      System.out.printf(
          "Bar %d - Price: %.2f, VWAP: %.2f%n",
          i,
          closePrice.getValue(i).doubleValue(),
          vwapIndicator.getValue(i).doubleValue());
    }

    // No entry signal during baseline
    assertThat(strategy.getEntryRule().isSatisfied(6)).isFalse();

    // Entry signal when price crosses above VWAP
    boolean entryFound = false;
    for (int i = 7; i <= 9; i++) {
      if (strategy.getEntryRule().isSatisfied(i)) {
        entryFound = true;
        System.out.println("Entry signal found at bar " + i);
        break;
      }
    }
    assertThat(entryFound).isTrue();
  }

  @Test
  public void exitRule_shouldTrigger_whenPriceCrossesBelowVwap() {
    // Log VWAP and price values around the expected cross-down
    for (int i = 10; i <= 13; i++) {
      System.out.printf(
          "Bar %d - Price: %.2f, VWAP: %.2f%n",
          i, closePrice.getValue(i).doubleValue(), vwapIndicator.getValue(i).doubleValue());
    }

    // No exit signal before the drop
    assertThat(strategy.getExitRule().isSatisfied(10)).isFalse();

    // Exit signal when price crosses below VWAP
    boolean exitFound = false;
    for (int i = 11; i <= 13; i++) {
      if (strategy.getExitRule().isSatisfied(i)) {
        exitFound = true;
        System.out.println("Exit signal found at bar " + i);
        break;
      }
    }
    assertThat(exitFound).isTrue();
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateVwapPeriod() throws InvalidProtocolBufferException {
    params =
        VwapCrossoverParameters.newBuilder()
            .setVwapPeriod(-1)
            .setMovingAveragePeriod(MA_PERIOD)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateMovingAveragePeriod() throws InvalidProtocolBufferException {
    params =
        VwapCrossoverParameters.newBuilder()
            .setVwapPeriod(VWAP_PERIOD)
            .setMovingAveragePeriod(-1)
            .build();
    factory.createStrategy(series, params);
  }

  @Test
  public void getDefaultParameters_returnsValidParameters() {
    VwapCrossoverParameters defaultParams = factory.getDefaultParameters();
    assertThat(defaultParams.getVwapPeriod()).isEqualTo(20);
    assertThat(defaultParams.getMovingAveragePeriod()).isEqualTo(20);
  }

  private BaseBar createBar(ZonedDateTime time, double price, double volume) {
    return new BaseBar(
        Duration.ofMinutes(1),
        time,
        price, // open
        price, // high
        price, // low
        price, // close
        volume);
  }
}
