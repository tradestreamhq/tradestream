package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.Range;
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
  private static final FluentLogger logger = FluentLogger.forEnclosingClass();

  private static final int SHORT_EMA = 2;
  private static final int LONG_EMA = 5;

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

    // Create indicators for logging
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator shortEmaInd = new EMAIndicator(closePrice, SHORT_EMA);
    EMAIndicator longEmaInd = new EMAIndicator(closePrice, LONG_EMA);

    // Log values for debugging
    logBarSeriesWithEma(series, shortEmaInd, longEmaInd);

    Strategy strategy = factory.createStrategy(series, params);
    BarSeriesManager manager = new BarSeriesManager(series);
    TradingRecord tradingRecord = manager.run(strategy);

    logTradingRecord(tradingRecord, series);

    logger.atInfo().log("Finished running strategy. Final position count: %d", 
        tradingRecord.getPositionCount());
    assertThat(tradingRecord.getPositionCount()).isGreaterThan(0);
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

    // Create local EMA indicators to observe values
    ClosePriceIndicator closePrice = new ClosePriceIndicator(series);
    EMAIndicator shortEmaInd = new EMAIndicator(closePrice, SHORT_EMA);
    EMAIndicator longEmaInd = new EMAIndicator(closePrice, LONG_EMA);

    logBarSeriesWithEma(series, shortEmaInd, longEmaInd);

    Strategy strategy = factory.createStrategy(series, params);
    BarSeriesManager manager = new BarSeriesManager(series);
    TradingRecord tradingRecord = manager.run(strategy);

    logTradingRecord(tradingRecord, series);

    // Verify exactly one completed position
    assertThat(tradingRecord.getPositionCount()).isEqualTo(1);

    Position position = tradingRecord.getPositions().get(0);
  
    // Entry should happen around when short EMA rises above long EMA (bars 7-8)
    assertThat(position.getEntry().getIndex()).isIn(Range.closed(7, 8));
  
    // Exit should happen around when short EMA drops below long EMA (bars 10-11)
    assertThat(position.getExit().getIndex()).isIn(Range.closed(10, 11));
  
    // Entry must come before exit
    assertThat(position.getEntry().getIndex())
        .isLessThan(position.getExit().getIndex());
  }

  private BarSeries createCrossUpSeries() {
    logger.atInfo().log("Creating bar series to test short EMA crossing up...");
    BarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Warm-up: 7 bars steady price to establish baseline EMAs
    for (int i = 0; i < 7; i++) {
        series.addBar(
            new BaseBar(
                Duration.ofMinutes(1),
                now.plusMinutes(i),
                50.0, 50.0, 50.0, 50.0,
                100.0));
    }

    // Sharp rise to trigger short EMA crossing above long EMA
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(7), 60.0, 60.0, 60.0, 60.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(8), 70.0, 70.0, 70.0, 70.0, 100.0));
    
    // Maintain higher levels to establish uptrend
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(9), 75.0, 75.0, 75.0, 75.0, 100.0));

    // Sharp drop to trigger short EMA crossing below long EMA
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(10), 45.0, 45.0, 45.0, 45.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(11), 40.0, 40.0, 40.0, 40.0, 100.0));

    logger.atInfo().log("createCrossUpSeries - Done creating series with dramatic price movements");
    return series;
  }

  private BarSeries createCrossDownSeries() {
    logger.atInfo().log("Creating bar series to test short EMA crossing down...");
    BarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Same pattern as crossUpSeries to first establish a position
    // Warm-up: 7 bars steady price to establish baseline EMAs
    for (int i = 0; i < 7; i++) {
        series.addBar(
            new BaseBar(
                Duration.ofMinutes(1),
                now.plusMinutes(i),
                50.0, 50.0, 50.0, 50.0,
                100.0));
    }

    // Sharp rise to trigger short EMA crossing above long EMA
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(7), 60.0, 60.0, 60.0, 60.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(8), 70.0, 70.0, 70.0, 70.0, 100.0));
    
    // Maintain higher levels briefly
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(9), 75.0, 75.0, 75.0, 75.0, 100.0));

    // Sharp drop to trigger short EMA crossing below long EMA
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(10), 45.0, 45.0, 45.0, 45.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(11), 40.0, 40.0, 40.0, 40.0, 100.0));
    
    // Keep low to establish downtrend
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(12), 35.0, 35.0, 35.0, 35.0, 100.0));

    logger.atInfo().log("createCrossDownSeries - Done creating series with dramatic price movements");
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
