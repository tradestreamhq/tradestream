package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import java.time.Duration;
import java.time.ZonedDateTime;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Position;
import org.ta4j.core.Strategy;
import org.ta4j.core.TradingRecord;
import org.ta4j.core.backtest.BarSeriesManager;

@RunWith(JUnit4.class)
public class DoubleEmaCrossoverStrategyFactoryTest {
  private static final Logger logger =
      Logger.getLogger(DoubleEmaCrossoverStrategyFactoryTest.class.getName());

  private static final int SHORT_EMA = 3;
  private static final int LONG_EMA = 7;

  @Inject private DoubleEmaCrossoverStrategyFactory factory;

  @Before
  public void setUp() {
    logger.info("Setting up test dependencies via Guice injector...");
    Guice.createInjector().injectMembers(this);
  }

  @Test
  public void getStrategyType_returnsCorrectType() {
    logger.info("Executing getStrategyType_returnsCorrectType test...");
    StrategyType strategyType = factory.getStrategyType();
    logger.log(Level.FINE, "StrategyType obtained: {0}", strategyType);

    assertThat(strategyType).isEqualTo(StrategyType.DOUBLE_EMA_CROSSOVER);
    logger.info("getStrategyType_returnsCorrectType test passed.");
  }

  @Test
  public void createStrategy_entryRule_triggersOnShortEmaCrossUp()
      throws InvalidProtocolBufferException {
    logger.info("Executing createStrategy_entryRule_triggersOnShortEmaCrossUp test...");
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters
          .newBuilder()
          .setShortEmaPeriod(SHORT_EMA)
          .setLongEmaPeriod(LONG_EMA)
          .build();
    logger.log(Level.FINE, "Parameters for short/long EMA: {0}", params);

    BarSeries series = createCrossUpSeries();
    Strategy strategy = factory.createStrategy(series, params);
    BarSeriesManager manager = new BarSeriesManager(series);
    TradingRecord tradingRecord = manager.run(strategy);

    logger.log(
        Level.FINE,
        "Finished running strategy. Position count: {0}",
        tradingRecord.getPositionCount());
    assertThat(tradingRecord.getPositionCount()).isGreaterThan(0);

    logger.info("createStrategy_entryRule_triggersOnShortEmaCrossUp test passed.");
  }

  @Test
  public void createStrategy_exitRule_triggersOnShortEmaCrossDown()
      throws InvalidProtocolBufferException {
    logger.info("Executing createStrategy_exitRule_triggersOnShortEmaCrossDown test...");
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters
          .newBuilder()
          .setShortEmaPeriod(SHORT_EMA)
          .setLongEmaPeriod(LONG_EMA)
          .build();
    logger.log(Level.FINE, "Parameters for short/long EMA: {0}", params);

    BarSeries series = createCrossDownSeries();
    Strategy strategy = factory.createStrategy(series, params);
    BarSeriesManager manager = new BarSeriesManager(series);
    TradingRecord tradingRecord = manager.run(strategy);

    logger.log(
        Level.FINE,
        "Finished running strategy. Position count: {0}",
        tradingRecord.getPositionCount());
    assertThat(tradingRecord.getPositionCount()).isEqualTo(1);

    Position position = tradingRecord.getPositions().get(0);
    logger.log(
        Level.FINE,
        "Validating that entry index ({0}) < exit index ({1})",
        new Object[] {position.getEntry().getIndex(), position.getExit().getIndex()});
    assertThat(position.getEntry().getIndex()).isLessThan(position.getExit().getIndex());

    logger.info("createStrategy_exitRule_triggersOnShortEmaCrossDown test passed.");
  }

  private BarSeries createCrossDownSeries() {
    logger.fine("Creating bar series to test short EMA crossing down...");
    BarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // 5 bars at 10 to establish a baseline
    for (int i = 0; i < 5; i++) {
      Bar bar = new BaseBar(
          Duration.ofMinutes(1),
          now.plusMinutes(i),
          10.0, 10.0, 10.0, 10.0,
          100.0);
      series.addBar(bar);
    }
  
    // Move up first, letting short EMA go above the long EMA
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(5), 15.0, 15.0, 15.0, 15.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(6), 20.0, 20.0, 20.0, 20.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(7), 25.0, 25.0, 25.0, 25.0, 100.0));
  
    // Stabilize a bit
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(8), 25.0, 25.0, 25.0, 25.0, 100.0));
  
    // Then a sharp drop—enough bars to ensure the cross down is recognized
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(9), 15.0, 15.0, 15.0, 15.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(10), 10.0, 10.0, 10.0, 10.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(11), 5.0, 5.0, 5.0, 5.0, 100.0));
  
    // One extra bar so TA4J sees the cross from the previous bar
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(12), 5.0, 5.0, 5.0, 5.0, 100.0));
  
    return series;
  }

  private BarSeries createCrossUpSeries() {
    logger.fine("Creating bar series to test short EMA crossing up...");
    BarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
  
    // 5 bars at 10 to establish baseline
    for (int i = 0; i < 5; i++) {
      Bar bar = new BaseBar(
          Duration.ofMinutes(1),
          now.plusMinutes(i),
          10.0, 10.0, 10.0, 10.0,
          100.0);
      series.addBar(bar);
    }
  
    // Gradually move upward to let short EMA inch above long EMA
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(5), 12.0, 12.0, 12.0, 12.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(6), 14.0, 14.0, 14.0, 14.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(7), 18.0, 18.0, 18.0, 18.0, 100.0));
  
    // IMPORTANT: One extra bar to confirm short > long *on the next bar*
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(8), 20.0, 20.0, 20.0, 20.0, 100.0));
  
    return series;
  }
}
