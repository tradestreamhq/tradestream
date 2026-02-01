package com.verlumen.tradestream.strategies.pricegap;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.PriceGapParameters;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class PriceGapStrategyFactoryTest {

  private final PriceGapStrategyFactory factory = new PriceGapStrategyFactory();
  private final BarSeries series = new BaseBarSeries();

  @Test
  public void getDefaultParameters_returnsCorrectParameters() {
    // Act
    PriceGapParameters result = factory.getDefaultParameters();

    // Assert
    assertThat(result).isNotNull();
    assertThat(result.getPeriod()).isEqualTo(10);
  }

  @Test
  public void createStrategy_returnsValidStrategy() throws Exception {
    // Arrange
    PriceGapParameters parameters = PriceGapParameters.newBuilder().setPeriod(15).build();

    // Act
    Strategy result = factory.createStrategy(series, parameters);

    // Assert
    assertThat(result).isNotNull();
    assertThat(result.getEntryRule()).isNotNull();
    assertThat(result.getExitRule()).isNotNull();
    assertThat(result.getName()).isEqualTo("Price Gap Strategy");
  }
}
