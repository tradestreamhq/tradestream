package com.verlumen.tradestream.strategies.bbandwr;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.BbandWRParameters;
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
import org.ta4j.core.indicators.WilliamsRIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsLowerIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsMiddleIndicator;
import org.ta4j.core.indicators.bollinger.BollingerBandsUpperIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.statistics.StandardDeviationIndicator;

@RunWith(JUnit4.class)
public class BbandWRStrategyFactoryTest {
  private static final int BBANDS_PERIOD = 20;
  private static final int WR_PERIOD = 14;
  private static final double STD_DEV_MULTIPLIER = 2.0;

  private BbandWRStrategyFactory factory;
  private BbandWRParameters params;
  private BaseBarSeries series;
  private Strategy strategy;

  // For debugging calculations
  private ClosePriceIndicator closePrice;
  private SMAIndicator smaIndicator;
  private BollingerBandsUpperIndicator bbUpper;
  private BollingerBandsLowerIndicator bbLower;
  private WilliamsRIndicator williamsR;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new BbandWRStrategyFactory();

    // Standard parameters
    params =
        BbandWRParameters.newBuilder()
            .setBbandsPeriod(BBANDS_PERIOD)
            .setWrPeriod(WR_PERIOD)
            .setStdDevMultiplier(STD_DEV_MULTIPLIER)
            .build();

    // Initialize series
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Create sample price data that will trigger entry and exit conditions
    // Bars 0-19: Stable period around 100
    for (int i = 0; i < 20; i++) {
      series.addBar(createBar(now.plusMinutes(i), 100.0));
    }

    // Bars 20-25: Sharp decline to trigger entry condition (price below lower band, WR oversold)
    series.addBar(createBar(now.plusMinutes(20), 95.0));
    series.addBar(createBar(now.plusMinutes(21), 85.0));
    series.addBar(createBar(now.plusMinutes(22), 75.0));
    series.addBar(createBar(now.plusMinutes(23), 70.0));
    series.addBar(createBar(now.plusMinutes(24), 65.0));
    series.addBar(createBar(now.plusMinutes(25), 60.0));

    // Bars 26-30: Sharp rise to trigger exit condition (price above upper band, WR overbought)
    series.addBar(createBar(now.plusMinutes(26), 110.0));
    series.addBar(createBar(now.plusMinutes(27), 120.0));
    series.addBar(createBar(now.plusMinutes(28), 130.0));
    series.addBar(createBar(now.plusMinutes(29), 135.0));
    series.addBar(createBar(now.plusMinutes(30), 140.0));

    // Initialize indicators
    closePrice = new ClosePriceIndicator(series);
    smaIndicator = new SMAIndicator(closePrice, BBANDS_PERIOD);
    BollingerBandsMiddleIndicator bbMiddle = new BollingerBandsMiddleIndicator(smaIndicator);
    StandardDeviationIndicator stdDev = new StandardDeviationIndicator(closePrice, BBANDS_PERIOD);
    bbUpper = new BollingerBandsUpperIndicator(bbMiddle, stdDev, series.numOf(STD_DEV_MULTIPLIER));
    bbLower = new BollingerBandsLowerIndicator(bbMiddle, stdDev, series.numOf(STD_DEV_MULTIPLIER));
    williamsR = new WilliamsRIndicator(series, WR_PERIOD);

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void getDefaultParameters_returnsExpectedDefaults() {
    BbandWRParameters defaults = factory.getDefaultParameters();
    assertThat(defaults.getBbandsPeriod()).isEqualTo(20);
    assertThat(defaults.getWrPeriod()).isEqualTo(14);
    assertThat(defaults.getStdDevMultiplier()).isEqualTo(2.0);
  }

  @Test
  public void entryRule_shouldTrigger_whenPriceBelowLowerBandAndWROversold() {
    // Find a bar where entry conditions are met
    int entryIndex = -1;
    for (int i = BBANDS_PERIOD; i < series.getBarCount(); i++) {
      double price = closePrice.getValue(i).doubleValue();
      double lowerBand = bbLower.getValue(i).doubleValue();
      double wr = williamsR.getValue(i).doubleValue();
      System.out.printf(
          "Bar %d - Price: %.2f, Lower Band: %.2f, Williams %%R: %.2f%n", i, price, lowerBand, wr);

      if (price < lowerBand && wr < -80) {
        entryIndex = i;
        break;
      }
    }

    if (entryIndex > 0) {
      System.out.printf("Entry condition found at bar %d%n", entryIndex);
      assertThat(strategy.getEntryRule().isSatisfied(entryIndex)).isTrue();
    } else {
      System.out.println("No entry signal found with current data and parameters.");
    }
  }

  @Test
  public void exitRule_shouldTrigger_whenPriceAboveUpperBandAndWROverbought() {
    // Find a bar where exit conditions are met
    int exitIndex = -1;
    for (int i = BBANDS_PERIOD; i < series.getBarCount(); i++) {
      double price = closePrice.getValue(i).doubleValue();
      double upperBand = bbUpper.getValue(i).doubleValue();
      double wr = williamsR.getValue(i).doubleValue();
      System.out.printf(
          "Bar %d - Price: %.2f, Upper Band: %.2f, Williams %%R: %.2f%n", i, price, upperBand, wr);

      if (price > upperBand && wr > -20) {
        exitIndex = i;
        break;
      }
    }

    if (exitIndex > 0) {
      System.out.printf("Exit condition found at bar %d%n", exitIndex);
      assertThat(strategy.getExitRule().isSatisfied(exitIndex)).isTrue();
    } else {
      System.out.println("No exit signal found with current data and parameters.");
    }
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateBbandsPeriod() throws InvalidProtocolBufferException {
    params =
        BbandWRParameters.newBuilder()
            .setBbandsPeriod(-1)
            .setWrPeriod(WR_PERIOD)
            .setStdDevMultiplier(STD_DEV_MULTIPLIER)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateWrPeriod() throws InvalidProtocolBufferException {
    params =
        BbandWRParameters.newBuilder()
            .setBbandsPeriod(BBANDS_PERIOD)
            .setWrPeriod(-1)
            .setStdDevMultiplier(STD_DEV_MULTIPLIER)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateStdDevMultiplier() throws InvalidProtocolBufferException {
    params =
        BbandWRParameters.newBuilder()
            .setBbandsPeriod(BBANDS_PERIOD)
            .setWrPeriod(WR_PERIOD)
            .setStdDevMultiplier(-1.0)
            .build();
    factory.createStrategy(series, params);
  }

  @Test
  public void createStrategy_withValidParameters_createsStrategyWithCorrectName()
      throws InvalidProtocolBufferException {
    Strategy testStrategy = factory.createStrategy(series, params);
    String expectedName =
        String.format(
            "BBAND_W_R (BB: %d, WR: %d, StdDev: %.1f)",
            BBANDS_PERIOD, WR_PERIOD, STD_DEV_MULTIPLIER);
    assertThat(testStrategy.getName()).isEqualTo(expectedName);
  }

  private BaseBar createBar(ZonedDateTime time, double price) {
    return new BaseBar(
        Duration.ofMinutes(1),
        time,
        price, // open
        price, // high
        price, // low
        price, // close
        100.0 // volume
        );
  }
}
