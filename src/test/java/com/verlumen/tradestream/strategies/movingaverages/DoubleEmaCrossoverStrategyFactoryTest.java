package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import java.time.Duration;
import java.time.ZonedDateTime;
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
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;

@RunWith(JUnit4.class)
public class DoubleEmaCrossoverStrategyFactoryTest {
  // Use Flogger:
  private static final FluentLogger logger = FluentLogger.forEnclosingClass();

  private static final int SHORT_EMA = 3;
  private static final int LONG_EMA = 7;

  @Inject private DoubleEmaCrossoverStrategyFactory factory;

  @Before
  public void setUp() {
    logger.atInfo().log("Setting up test dependencies via Guice injector...");
    Guice.createInjector().injectMembers(this);
  }

  @Test
  public void getStrategyType_returnsCorrectType() {
    logger.atInfo().log("Executing getStrategyType_returnsCorrectType test...");
    StrategyType strategyType = factory.getStrategyType();
    logger.atInfo().log("StrategyType obtained: %s", strategyType);

    assertThat(strategyType).isEqualTo(StrategyType.DOUBLE_EMA_CROSSOVER);
    logger.atInfo().log("getStrategyType_returnsCorrectType test passed.");
  }

  @Test
  public void createStrategy_entryRule_triggersOnShortEmaCrossUp()
      throws InvalidProtocolBufferException {
    logger.atInfo().log("Executing createStrategy_entryRule_triggersOnShortEmaCrossUp test...");
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setLongEmaPeriod(LONG_EMA)
            .build();
    logger.atInfo().log("Parameters for short/long EMA: %s", params);

    BarSeries series = createCrossUpSeries();

    // We'll create an EMAIndicator in the test, just to log how the EMA values progress.
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator shortEmaInd = new EMAIndicator(closePrice, SHORT_EMA);
    EMAIndicator longEmaInd = new EMAIndicator(closePrice, LONG_EMA);

    // Log bars/EMA
    logBarSeriesWithEma(series, shortEmaInd, longEmaInd);

    Strategy strategy = factory.createStrategy(series, params);
    BarSeriesManager manager = new BarSeriesManager(series);
    TradingRecord tradingRecord = manager.run(strategy);

    // Log final trading record
    logTradingRecord(tradingRecord, series);

    logger.atInfo().log("Finished running strategy. Final position count: %d",
        tradingRecord.getPositionCount());
    assertThat(tradingRecord.getPositionCount()).isGreaterThan(0);

    logger.atInfo().log("createStrategy_entryRule_triggersOnShortEmaCrossUp test passed.");
  }

  @Test
  public void createStrategy_exitRule_triggersOnShortEmaCrossDown()
      throws InvalidProtocolBufferException {
    logger.atInfo().log("Executing createStrategy_exitRule_triggersOnShortEmaCrossDown test...");
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setLongEmaPeriod(LONG_EMA)
            .build();
    logger.atInfo().log("Parameters for short/long EMA: %s", params);

    BarSeries series = createCrossDownSeries();

    // Again, create local EMA indicators to observe values per bar
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator shortEmaInd = new EMAIndicator(closePrice, SHORT_EMA);
    EMAIndicator longEmaInd = new EMAIndicator(closePrice, LONG_EMA);

    logBarSeriesWithEma(series, shortEmaInd, longEmaInd);

    Strategy strategy = factory.createStrategy(series, params);
    BarSeriesManager manager = new BarSeriesManager(series);
    TradingRecord tradingRecord = manager.run(strategy);

    logTradingRecord(tradingRecord, series);

    logger.atInfo().log("Finished running strategy. Final position count: %d",
        tradingRecord.getPositionCount());
    assertThat(tradingRecord.getPositionCount()).isEqualTo(1);

    Position position = tradingRecord.getPositions().get(0);
    logger.atInfo().log(
        "Validating that entry index (%d) < exit index (%d)",
        position.getEntry().getIndex(),
        position.getExit().getIndex());
    assertThat(position.getEntry().getIndex()).isLessThan(position.getExit().getIndex());

    logger.atInfo().log("createStrategy_exitRule_triggersOnShortEmaCrossDown test passed.");
  }

  /**
   * Creates a bar series designed to produce a short-EMA cross UP over the long-EMA.
   */
  private BarSeries createCrossUpSeries() {
    logger.atInfo().log("Creating bar series to test short EMA crossing up...");
    BarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // 1) Warm-up bars so the short (3) & long (7) EMAs are valid.
    //    10 bars at 10.0 to "prime" the EMAs.
    for (int i = 0; i < 10; i++) {
      series.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              10.0, 10.0, 10.0, 10.0,
              100.0));
    }

    // 2) Gradually increase price so shortEma eventually crosses above longEma.
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(10), 12.0, 12.0, 12.0, 12.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(11), 14.0, 14.0, 14.0, 14.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(12), 18.0, 18.0, 18.0, 18.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(13), 20.0, 20.0, 20.0, 20.0, 100.0));

    // 3) Add extra bars so TA4J can “finalize” the cross.
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(14), 20.0, 20.0, 20.0, 20.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(15), 20.0, 20.0, 20.0, 20.0, 100.0));

    logger.atInfo().log("createCrossUpSeries - Completed building bar series for cross-up scenario.");
    return series;
  }

  /**
   * Creates a bar series designed to produce a short-EMA cross DOWN below the long-EMA.
   */
  private BarSeries createCrossDownSeries() {
    logger.atInfo().log("Creating bar series to test short EMA crossing down...");
    BarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // 1) Warm-up bars
    for (int i = 0; i < 10; i++) {
      series.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i),
              10.0, 10.0, 10.0, 10.0,
              100.0));
    }

    // 2) Move up first (shortEma > longEma)
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(10), 15.0, 15.0, 15.0, 15.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(11), 20.0, 20.0, 20.0, 20.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(12), 25.0, 25.0, 25.0, 25.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(13), 25.0, 25.0, 25.0, 25.0, 100.0));

    // 3) Then drop so shortEma < longEma
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(14), 15.0, 15.0, 15.0, 15.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(15), 10.0, 10.0, 10.0, 10.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(16), 5.0, 5.0, 5.0, 5.0, 100.0));

    // 4) Extra trailing bars for final cross detection
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(17), 5.0, 5.0, 5.0, 5.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(18), 5.0, 5.0, 5.0, 5.0, 100.0));

    logger.atInfo().log(
        "createCrossDownSeries - Completed building bar series for cross-down scenario.");
    return series;
  }

  /**
   * Logs each bar’s open/high/low/close plus short and long EMA values for debugging.
   */
  private void logBarSeriesWithEma(
      BarSeries series, EMAIndicator shortEmaInd, EMAIndicator longEmaInd) {
    logger.atInfo().log("Logging bar data + short/long EMA values for debugging:");
    for (int i = 0; i < series.getBarCount(); i++) {
      Bar bar = series.getBar(i);
      double shortVal = shortEmaInd.getValue(i).doubleValue();
      double longVal = longEmaInd.getValue(i).doubleValue();
      logger.atInfo().log(
          "Bar[%d] time=%s O=%.4f,H=%.4f,L=%.4f,C=%.4f shortEma=%.4f longEma=%.4f",
          i,
          bar.getEndTime(),
          bar.getOpenPrice().doubleValue(),
          bar.getHighPrice().doubleValue(),
          bar.getLowPrice().doubleValue(),
          bar.getClosePrice().doubleValue(),
          shortVal,
          longVal);
    }
  }

  /**
   * Logs the trading record: final position count, positions with entry/exit bar indexes.
   */
  private void logTradingRecord(TradingRecord tradingRecord, BarSeries series) {
    int count = tradingRecord.getPositionCount();
    logger.atInfo().log("Logging TradingRecord details... Position count=%d", count);

    if (count == 0) {
      logger.atInfo().log("-- No positions in this trading record. Possibly no crosses detected. --");
      return;
    }

    for (int p = 0; p < count; p++) {
      Position pos = tradingRecord.getPositions().get(p);
      logger.atInfo().log("Position #%d: entry=%s exit=%s", p, pos.getEntry(), pos.getExit());
      logger.atInfo().log(
          "Entry bar idx=%d closePrice=%.4f; Exit bar idx=%d closePrice=%.4f",
          pos.getEntry().getIndex(),
          series.getBar(pos.getEntry().getIndex()).getClosePrice().doubleValue(),
          pos.getExit().getIndex(),
          series.getBar(pos.getExit().getIndex()).getClosePrice().doubleValue());
    }
  }
}
