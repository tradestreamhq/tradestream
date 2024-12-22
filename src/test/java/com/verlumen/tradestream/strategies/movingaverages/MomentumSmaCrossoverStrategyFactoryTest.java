package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.MomentumSmaCrossoverParameters;
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
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.MomentumIndicator;

@RunWith(JUnit4.class)
public class MomentumSmaCrossoverStrategyFactoryTest {
  private static final int MOMENTUM_PERIOD = 10;
  private static final int SMA_PERIOD = 20;
  private MomentumSmaCrossoverStrategyFactory factory;
  private MomentumSmaCrossoverParameters params;
    private BaseBarSeries series;
    private Strategy strategy;

  // For debugging EMA calculations
  private MomentumIndicator momentumIndicator;
  private SMAIndicator smaIndicator;
  private ClosePriceIndicator closePrice;


  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new MomentumSmaCrossoverStrategyFactory();
      params = MomentumSmaCrossoverParameters.newBuilder()
          .setMomentumPeriod(MOMENTUM_PERIOD)
          .setSmaPeriod(SMA_PERIOD)
          .build();

      // Initialize series
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    
       // ---------------------------------------------------------------------
        // 1) Baseline - momentum < sma
        // ---------------------------------------------------------------------
       double price = 50.0;
       for (int i = 0; i < 7; i++) {
           series.addBar(createBar(now.plusMinutes(i), price));
          price -= 1.0;
        }

       // ---------------------------------------------------------------------
        // 2) Upward movement - momentum > sma by bar 7
        // ---------------------------------------------------------------------
      series.addBar(createBar(now.plusMinutes(7), 65.0));
      series.addBar(createBar(now.plusMinutes(8), 80.0));
      series.addBar(createBar(now.plusMinutes(9), 85.0));
      series.addBar(createBar(now.plusMinutes(10), 90.0));


        // ---------------------------------------------------------------------
        // 3) Downward movement - momentum < sma by bar 11
        // ---------------------------------------------------------------------
      series.addBar(createBar(now.plusMinutes(11), 40.0));
      series.addBar(createBar(now.plusMinutes(12), 30.0));
        series.addBar(createBar(now.plusMinutes(13), 25.0));

    // Initialize indicators for debugging
    closePrice = new ClosePriceIndicator(series);
    momentumIndicator = new MomentumIndicator(closePrice, MOMENTUM_PERIOD);
    smaIndicator = new SMAIndicator(momentumIndicator, SMA_PERIOD);

        // Create strategy
      strategy = factory.createStrategy(series, params);
  }

    @Test
    public void getStrategyType_returnsMomentumSmaCrossover() {
        assertThat(factory.getStrategyType()).isEqualTo(StrategyType.MOMENTUM_SMA_CROSSOVER);
    }


  @Test
    public void entryRule_shouldTrigger_whenMomentumCrossesAboveSma() {
       for (int i = 6; i <= 10; i++) {
         System.out.printf("Bar %d - Price: %.2f, Momentum: %.2f, SMA: %.2f%n",
              i,
              closePrice.getValue(i).doubleValue(),
              momentumIndicator.getValue(i).doubleValue(),
              smaIndicator.getValue(i).doubleValue());
      }

       // No entry signal before crossover
        assertFalse("Should not trigger entry at bar 6", strategy.getEntryRule().isSatisfied(6));


      // Entry signal at bar 7
      assertTrue(
           "Entry rule should trigger when momentum crosses above SMA at bar 7",
           strategy.getEntryRule().isSatisfied(7)
      );
    }

    @Test
    public void exitRule_shouldTrigger_whenMomentumCrossesBelowSma() {
      for (int i = 10; i <= 13; i++) {
        System.out.printf("Bar %d - Price: %.2f, Momentum: %.2f, SMA: %.2f%n",
              i,
              closePrice.getValue(i).doubleValue(),
                momentumIndicator.getValue(i).doubleValue(),
              smaIndicator.getValue(i).doubleValue());
      }

      // No exit signal before crossover
        assertFalse("Should not trigger exit at bar 10", strategy.getExitRule().isSatisfied(10));

        // Exit signal at bar 11
        assertTrue(
            "Exit rule should trigger when momentum crosses below SMA at bar 11",
            strategy.getExitRule().isSatisfied(11)
        );
    }


  @Test(expected = IllegalArgumentException.class)
  public void validateMomentumPeriod() throws InvalidProtocolBufferException {
      params = MomentumSmaCrossoverParameters.newBuilder().setMomentumPeriod(-1).setSmaPeriod(SMA_PERIOD).build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateSmaPeriod() throws InvalidProtocolBufferException {
    params = MomentumSmaCrossoverParameters.newBuilder().setMomentumPeriod(MOMENTUM_PERIOD).setSmaPeriod(-1).build();
    factory.createStrategy(series, params);
  }
  
   private BaseBar createBar(ZonedDateTime time, double price) {
        return new BaseBar(
            Duration.ofMinutes(1),
            time,
            price, // open
            price, // high
            price, // low
            price, // close
            100.0  // volume
        );
    }
}
