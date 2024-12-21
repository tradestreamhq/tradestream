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
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;

@RunWith(JUnit4.class)
public class DoubleEmaCrossoverStrategyFactoryTest {

  @Inject private DoubleEmaCrossoverStrategyFactory factory;

  @Before
  public void setUp() {
    Guice.createInjector().injectMembers(this);
  }

  @Test
  public void getStrategyType_returnsCorrectType() {
    // Arrange & Act
    StrategyType strategyType = factory.getStrategyType();

    // Assert
    assertThat(strategyType).isEqualTo(StrategyType.DOUBLE_EMA_CROSSOVER);
  }

  @Test
  public void createStrategy_entryRule_isCrossedUpIndicatorRule()
      throws InvalidProtocolBufferException {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(5).setLongEmaPeriod(20).build();
    BarSeries series = createTestBarSeries();

    // Act
    Strategy strategy = factory.createStrategy(series, params);

    // Assert
    // We can still verify the type of the entry rule
    assertThat(strategy.getEntryRule()).isInstanceOf(CrossedUpIndicatorRule.class);
  }

  @Test
  public void createStrategy_exitRule_isCrossedDownIndicatorRule()
      throws InvalidProtocolBufferException {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(5).setLongEmaPeriod(20).build();
    BarSeries series = createTestBarSeries();

    // Act
    Strategy strategy = factory.createStrategy(series, params);

    // Assert
    assertThat(strategy.getExitRule()).isInstanceOf(CrossedDownIndicatorRule.class);
  }

  /**
   * A more functional test verifying that the entry rule is satisfied at the correct index after
   * short EMA crosses above long EMA.
   *
   * <p>Note: This requires creating a BarSeries that actually triggers a cross-up if shortEmaPeriod <
   * longEmaPeriod.
   */
  @Test
  public void createStrategy_entryRule_triggersOnShortEmaCrossUp()
      throws InvalidProtocolBufferException {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder()
            // Use smaller periods so the crossover can happen quickly
            .setShortEmaPeriod(2)
            .setLongEmaPeriod(3)
            .build();

    // This series (below) is engineered so that around the last bar,
    // the short EMA (2) crosses above the long EMA (3) at index 3.
    BarSeries series = createCrossUpSeries();
    Strategy strategy = factory.createStrategy(series, params);

    // Act & Assert
    // We'll test that the entry rule becomes true at some bar
    boolean entrySatisfiedAtIndex = false;
    for (int i = series.getBeginIndex(); i <= series.getEndIndex(); i++) {
      if (strategy.getEntryRule().isSatisfied(i)) {
        entrySatisfiedAtIndex = true;
        break;
      }
    }
    // Because we've engineered the data to cross, we expect at least one bar to trigger
    assertThat(entrySatisfiedAtIndex).isTrue();
  }

  /**
   * A more functional test verifying that the exit rule is satisfied at the correct index after short
   * EMA crosses below long EMA.
   */
  @Test
  public void createStrategy_exitRule_triggersOnShortEmaCrossDown()
      throws InvalidProtocolBufferException {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(2).setLongEmaPeriod(3).build();
    BarSeries series = createCrossDownSeries();

    // Act
    Strategy strategy = factory.createStrategy(series, params);
    BarSeriesManager manager = new BarSeriesManager(series);
    TradingRecord tradingRecord = manager.run(strategy);

    // Assert
    // Should enter position when short EMA crosses above long EMA
    // and exit when it crosses below
    assertThat(tradingRecord.getPositionCount()).isEqualTo(1);
    Position position = tradingRecord.getPositions().get(0);
    assertThat(position.getEntry().getIndex()).isLessThan(position.getExit().getIndex());
  }

  private BarSeries createTestBarSeries() {
    BarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // With newer TA4j, we must supply (Duration, endTime, open, high, low, close, volume)
    // Below is just an example with arbitrary values
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(1), 10.0, 12.0, 8.0, 11.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(2), 11.0, 13.0, 9.0, 12.0, 120.0));

    return series;
  }

  /**
   * Series designed so that short EMA crosses up the long EMA. The short period is 2, and the long
   * is 3, so around the last bar the short EMA rises above the long.
   *
   * <p>Crossover is expected at index 3.
   */
  private BarSeries createCrossUpSeries() {
    BarSeries series = new BaseBarSeries();

    ZonedDateTime now = ZonedDateTime.now();

    // For the first few bars, keep the close price steady or slightly decreasing
    // Then spike upward so that short EMA crosses above the long EMA
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(1), 10.0, 10.0, 10.0, 10.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(2), 10.0, 10.0, 10.0, 10.0, 100.0));
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(3), 9.5, 9.5, 9.0, 9.0, 100.0));
    // Big jump
    series.addBar(
        new BaseBar(Duration.ofMinutes(1), now.plusMinutes(4), 10.0, 15.0, 10.0, 15.0, 100.0));

    return series;
  }

  private BarSeries createCrossDownSeries() {
      BarSeries series = new BaseBarSeries();
      ZonedDateTime now = ZonedDateTime.now();

      // Initial steady price to establish baseline EMAs (3+ bars for stability)
      series.addBar(new BaseBar(Duration.ofMinutes(1), now, 10.0, 10.0, 10.0, 10.0, 100.0));
      series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(1), 10.0, 10.0, 10.0, 10.0, 100.0));
      series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(2), 10.0, 10.0, 10.0, 10.0, 100.0));
      series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(3), 10.0, 10.0, 10.0, 10.0, 100.0));

      // Strong upward movement to get short EMA above long EMA
      series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(4), 20.0, 20.0, 20.0, 20.0, 100.0));
      series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(5), 25.0, 25.0, 25.0, 25.0, 100.0));
      series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(6), 30.0, 30.0, 30.0, 30.0, 100.0));

      // Sharp decline to trigger short EMA crossing below long EMA
      series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(7), 15.0, 15.0, 15.0, 15.0, 100.0));
      series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(8), 10.0, 10.0, 10.0, 10.0, 100.0));
      series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(9), 5.0, 5.0, 5.0, 5.0, 100.0));

      return series;
  }
}
