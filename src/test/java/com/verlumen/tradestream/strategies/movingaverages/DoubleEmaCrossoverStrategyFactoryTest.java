package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;

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

@RunWith(JUnit4.class)
public class DoubleEmaCrossoverStrategyFactoryTest {

  @Inject private DoubleEmaCrossoverStrategyFactory factory;

  @Before
  public void setUp() {
    Guice.createInjector().injectMembers(this);
  }

  @Test
  public void getStrategyType_returnsCorrectType() {
    StrategyType strategyType = factory.getStrategyType();
    assertThat(strategyType).isEqualTo(StrategyType.DOUBLE_EMA_CROSSOVER);
  }

  @Test
  public void createStrategy_entryRule_triggersOnShortEmaCrossUp()
      throws InvalidProtocolBufferException {
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(2).setLongEmaPeriod(3).build();
    BarSeries series = createCrossUpSeries();
    Strategy strategy = factory.createStrategy(series, params);
    BarSeriesManager manager = new BarSeriesManager(series);
    TradingRecord tradingRecord = manager.run(strategy);
    
    assertThat(tradingRecord.getPositionCount()).isGreaterThan(0);
  }

  @Test
  public void createStrategy_exitRule_triggersOnShortEmaCrossDown()
      throws InvalidProtocolBufferException {
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(2).setLongEmaPeriod(3).build();
    BarSeries series = createCrossDownSeries();

    Strategy strategy = factory.createStrategy(series, params);
    BarSeriesManager manager = new BarSeriesManager(series);
    TradingRecord tradingRecord = manager.run(strategy);

    assertThat(tradingRecord.getPositionCount()).isEqualTo(1);
    Position position = tradingRecord.getPositions().get(0);
    assertThat(position.getEntry().getIndex()).isLessThan(position.getExit().getIndex());
  }

  private BarSeries createCrossDownSeries() {
    BarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Establish a baseline with steady low price
    for (int i = 0; i < 5; i++) {
      series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(i), 10.0, 10.0, 10.0, 10.0, 100.0));
    }

    // Sharp upward movement to trigger short EMA crossing above long EMA
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(5), 20.0, 20.0, 20.0, 20.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(6), 25.0, 25.0, 25.0, 25.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(7), 30.0, 30.0, 30.0, 30.0, 100.0));

    // Hold at higher level briefly
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(8), 30.0, 30.0, 30.0, 30.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(9), 30.0, 30.0, 30.0, 30.0, 100.0));

    // Sharp decline to trigger short EMA crossing below long EMA
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(10), 15.0, 15.0, 15.0, 15.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(11), 10.0, 10.0, 10.0, 10.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(12), 5.0, 5.0, 5.0, 5.0, 100.0));

    return series;
  }

  private BarSeries createCrossUpSeries() {
    BarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Start with steady prices to establish baseline EMAs
    for (int i = 0; i < 5; i++) {
        series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(i), 10.0, 10.0, 10.0, 10.0, 100.0));
    }

    // Sharp upward movement to trigger cross up
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(5), 15.0, 15.0, 15.0, 15.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(6), 20.0, 20.0, 20.0, 20.0, 100.0));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(7), 25.0, 25.0, 25.0, 25.0, 100.0));

    return series;
  }
}
