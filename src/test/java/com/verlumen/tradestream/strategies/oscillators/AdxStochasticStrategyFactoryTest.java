package com.verlumen.tradestream.strategies.oscillators;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.AdxStochasticParameters;
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
import org.ta4j.core.indicators.ADXIndicator;
import org.ta4j.core.indicators.StochasticOscillatorKIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;

@RunWith(JUnit4.class)
public class AdxStochasticStrategyFactoryTest {
  private static final int ADX_PERIOD = 14;
  private static final int STOCHASTIC_K_PERIOD = 14;
  private static final int STOCHASTIC_D_PERIOD = 3;
  private static final int OVERBOUGHT_THRESHOLD = 80;
  private static final int OVERSOLD_THRESHOLD = 20;

  private AdxStochasticStrategyFactory factory;
  private AdxStochasticParameters params;
  private BaseBarSeries series;
    private Strategy strategy;

  // For debugging ADX and Stochastic calculations
    private ADXIndicator adxIndicator;
    private StochasticOscillatorKIndicator stochasticOscillatorK;
    private ClosePriceIndicator closePrice;


  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new AdxStochasticStrategyFactory();

      params =
          AdxStochasticParameters.newBuilder()
              .setAdxPeriod(ADX_PERIOD)
              .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
              .setStochasticDPeriod(STOCHASTIC_D_PERIOD)
              .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
              .setOversoldThreshold(OVERSOLD_THRESHOLD)
              .build();
      // Initialize series
      series = new BaseBarSeries();
      ZonedDateTime now = ZonedDateTime.now();

      // ---------------------------------------------------------------------
      // 1) Baseline: ADX should be < 25, Stochastic > oversold by bar 6
      // ---------------------------------------------------------------------
      // Bar 0 to 6: descending prices: 50 -> 49 -> 48 -> 47 -> 46 -> 45 -> 44
      double price = 50.0;
      for (int i = 0; i < 7; i++) {
          series.addBar(createBar(now.plusMinutes(i), price));
          price -= 1.0;
      }


      // ---------------------------------------------------------------------
      // 2) ADX > 25, Stochastic is oversold. Should trigger at bar 7
      // ---------------------------------------------------------------------
      series.addBar(createBar(now.plusMinutes(7), 65.0));
      series.addBar(createBar(now.plusMinutes(8), 80.0));
      series.addBar(createBar(now.plusMinutes(9), 85.0));
      series.addBar(createBar(now.plusMinutes(10), 90.0));

      // ---------------------------------------------------------------------
      // 3) Then a strong downward movement forces stochastic to overbought
      //  or ADX to < 25. Should trigger at bar 11
      // ---------------------------------------------------------------------
        series.addBar(createBar(now.plusMinutes(11), 40.0));
        series.addBar(createBar(now.plusMinutes(12), 30.0));
        series.addBar(createBar(now.plusMinutes(13), 25.0));
      // Initialize indicators for debugging
        closePrice = new ClosePriceIndicator(series);
        adxIndicator = new ADXIndicator(closePrice, ADX_PERIOD);
        stochasticOscillatorK = new StochasticOscillatorKIndicator(closePrice, STOCHASTIC_K_PERIOD);

      // Create strategy
        strategy = factory.createStrategy(series, params);
  }

  @Test
  public void getStrategyType_returnsAdxStochastic() {
    assertThat(factory.getStrategyType()).isEqualTo(StrategyType.ADX_STOCHASTIC);
  }

    @Test
    public void entryRule_shouldTrigger_whenAdxIsOver25AndStochasticIsOversold() {
      // Log values around the expected entry
      for (int i = 6; i <= 9; i++) {
          System.out.printf("Bar %d - Price: %.2f, ADX: %.2f, Stochastic: %.2f%n",
              i,
              closePrice.getValue(i).doubleValue(),
              adxIndicator.getValue(i).doubleValue(),
                stochasticOscillatorK.getValue(i).doubleValue());
      }


        assertFalse("Should not trigger entry at bar 6", strategy.getEntryRule().isSatisfied(6));

        // Strict cross-up typically recognized at bar 7
        assertTrue(
            "Entry rule should trigger when ADX > 25 and stochastic is oversold at bar 7",
            strategy.getEntryRule().isSatisfied(7)
        );
    }

    @Test
    public void exitRule_shouldTrigger_whenAdxIsUnder25OrStochasticIsOverbought() {
      // Log values around the expected exit
        for (int i = 10; i <= 13; i++) {
          System.out.printf("Bar %d - Price: %.2f, ADX: %.2f, Stochastic: %.2f%n",
              i,
              closePrice.getValue(i).doubleValue(),
              adxIndicator.getValue(i).doubleValue(),
                stochasticOscillatorK.getValue(i).doubleValue());
      }

        // No exit signal before the drop
        assertFalse("Should not trigger exit at bar 10", strategy.getExitRule().isSatisfied(10));

        // Strict cross-down typically recognized at bar 11
      assertTrue(
            "Exit rule should trigger when ADX < 25 or stochastic is overbought at bar 11",
            strategy.getExitRule().isSatisfied(11)
        );
    }

  @Test(expected = IllegalArgumentException.class)
  public void validateAdxPeriod() throws InvalidProtocolBufferException {
    params =
        AdxStochasticParameters.newBuilder()
            .setAdxPeriod(-1)
            .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
            .setStochasticDPeriod(STOCHASTIC_D_PERIOD)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();
      factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateStochasticKPeriod() throws InvalidProtocolBufferException {
    params =
        AdxStochasticParameters.newBuilder()
            .setAdxPeriod(ADX_PERIOD)
            .setStochasticKPeriod(-1)
            .setStochasticDPeriod(STOCHASTIC_D_PERIOD)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateStochasticDPeriod() throws InvalidProtocolBufferException {
    params =
        AdxStochasticParameters.newBuilder()
            .setAdxPeriod(ADX_PERIOD)
            .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
            .setStochasticDPeriod(-1)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();
    factory.createStrategy(series, params);
  }

    @Test(expected = IllegalArgumentException.class)
    public void validateOversoldThreshold() throws InvalidProtocolBufferException {
        params =
            AdxStochasticParameters.newBuilder()
