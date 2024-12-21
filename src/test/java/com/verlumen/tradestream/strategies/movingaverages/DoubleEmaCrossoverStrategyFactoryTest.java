package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.rules.CrossedDownIndicatorRule;
import org.ta4j.core.rules.CrossedUpIndicatorRule;
import org.threeten.bp.Duration;
import org.threeten.bp.ZonedDateTime;

@RunWith(JUnit4.class)
public class DoubleEmaCrossoverStrategyFactoryTest {

  @Inject
  private DoubleEmaCrossoverStrategyFactory factory;

  @Before
  public void setUp() {
    Guice.createInjector().injectMembers(this);
  }

  @Test
  public void getStrategyType_returnsCorrectType() {
    // Arrange
    // Act
    StrategyType strategyType = factory.getStrategyType();

    // Assert
    assertThat(strategyType).isEqualTo(StrategyType.DOUBLE_EMA_CROSSOVER);
  }

  @Test
  public void createStrategy_entryRule_isCrossedUpIndicatorRule() throws InvalidProtocolBufferException {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(5).setLongEmaPeriod(20).build();
    BarSeries series = createTestBarSeries();

    // Act
    Strategy strategy = factory.createStrategy(series, params);

    // Assert
    assertThat(strategy.getEntryRule()).isInstanceOf(CrossedUpIndicatorRule.class);
  }

  @Test
  public void createStrategy_entryRule_usesShortEmaIndicator() throws InvalidProtocolBufferException {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(5).setLongEmaPeriod(20).build();
    BarSeries series = createTestBarSeries();

    // Act
    Strategy strategy = factory.createStrategy(series, params);
    CrossedUpIndicatorRule entryRule = (CrossedUpIndicatorRule) strategy.getEntryRule();

    // Assert
      assertThat(entryRule.getFirstIndicator()).isInstanceOf(EMAIndicator.class);
    EMAIndicator shortEma = (EMAIndicator) entryRule.getFirstIndicator();
    assertThat(shortEma.getTimeFrame()).isEqualTo(params.getShortEmaPeriod());
    assertThat(shortEma.getBarSeries()).isEqualTo(series);
  }

  @Test
  public void createStrategy_entryRule_usesLongEmaIndicator() throws InvalidProtocolBufferException {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(5).setLongEmaPeriod(20).build();
    BarSeries series = createTestBarSeries();

    // Act
    Strategy strategy = factory.createStrategy(series, params);
    CrossedUpIndicatorRule entryRule = (CrossedUpIndicatorRule) strategy.getEntryRule();

    // Assert
      assertThat(entryRule.getSecondIndicator()).isInstanceOf(EMAIndicator.class);
    EMAIndicator longEma = (EMAIndicator) entryRule.getSecondIndicator();
      assertThat(longEma.getTimeFrame()).isEqualTo(params.getLongEmaPeriod());
      assertThat(longEma.getBarSeries()).isEqualTo(series);
  }

  @Test
  public void createStrategy_exitRule_isCrossedDownIndicatorRule() throws InvalidProtocolBufferException {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(5).setLongEmaPeriod(20).build();
    BarSeries series = createTestBarSeries();

    // Act
    Strategy strategy = factory.createStrategy(series, params);

    // Assert
    assertThat(strategy.getExitRule()).isInstanceOf(CrossedDownIndicatorRule.class);
  }

  @Test
  public void createStrategy_exitRule_usesShortEmaIndicator() throws InvalidProtocolBufferException {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(5).setLongEmaPeriod(20).build();
    BarSeries series = createTestBarSeries();

    // Act
    Strategy strategy = factory.createStrategy(series, params);
    CrossedDownIndicatorRule exitRule = (CrossedDownIndicatorRule) strategy.getExitRule();

    // Assert
      assertThat(exitRule.getFirstIndicator()).isInstanceOf(EMAIndicator.class);
    EMAIndicator shortEma = (EMAIndicator) exitRule.getFirstIndicator();
      assertThat(shortEma.getTimeFrame()).isEqualTo(params.getShortEmaPeriod());
      assertThat(shortEma.getBarSeries()).isEqualTo(series);
  }

  @Test
  public void createStrategy_exitRule_usesLongEmaIndicator() throws InvalidProtocolBufferException {
    // Arrange
    DoubleEmaCrossoverParameters params =
        DoubleEmaCrossoverParameters.newBuilder().setShortEmaPeriod(5).setLongEmaPeriod(20).build();
    BarSeries series = createTestBarSeries();

    // Act
    Strategy strategy = factory.createStrategy(series, params);
    CrossedDownIndicatorRule exitRule = (CrossedDownIndicatorRule) strategy.getExitRule();

    // Assert
    assertThat(exitRule.getSecondIndicator()).isInstanceOf(EMAIndicator.class);
    EMAIndicator longEma = (EMAIndicator) exitRule.getSecondIndicator();
    assertThat(longEma.getTimeFrame()).isEqualTo(params.getLongEmaPeriod());
    assertThat(longEma.getBarSeries()).isEqualTo(series);
  }

  private BarSeries createTestBarSeries() {
    BarSeries series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(1), 10, 12, 8, 11));
    series.addBar(new BaseBar(Duration.ofMinutes(1), now.plusMinutes(2), 11, 13, 9, 12));
    return series;
  }
}
