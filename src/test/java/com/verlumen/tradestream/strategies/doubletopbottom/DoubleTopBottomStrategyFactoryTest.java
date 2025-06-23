package com.verlumen.tradestream.strategies.doubletopbottom;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.Any;
import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DoubleTopBottomParameters;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class DoubleTopBottomStrategyFactoryTest {

  private final DoubleTopBottomStrategyFactory factory = new DoubleTopBottomStrategyFactory();
  private final BarSeries series = new BaseBarSeries();

  @Test
  public void getDefaultParameters_returnsCorrectParameters() {
    // Act
    DoubleTopBottomParameters result = factory.getDefaultParameters();

    // Assert
    assertThat(result.getPeriod()).isEqualTo(20);
  }

  @Test
  public void createStrategy_withValidParameters_returnsStrategy()
      throws InvalidProtocolBufferException {
    // Arrange
    DoubleTopBottomParameters parameters =
        DoubleTopBottomParameters.newBuilder().setPeriod(15).build();

    // Act
    Strategy result = factory.createStrategy(series, parameters);

    // Assert
    assertThat(result).isNotNull();
    assertThat(result.getEntryRule()).isNotNull();
    assertThat(result.getExitRule()).isNotNull();
  }

  @Test
  public void createStrategy_withAnyParameters_returnsStrategy()
      throws InvalidProtocolBufferException {
    // Arrange
    DoubleTopBottomParameters parameters =
        DoubleTopBottomParameters.newBuilder().setPeriod(25).build();
    Any anyParameters = Any.pack(parameters);

    // Act
    Strategy result = factory.createStrategy(series, anyParameters);

    // Assert
    assertThat(result).isNotNull();
    assertThat(result.getEntryRule()).isNotNull();
    assertThat(result.getExitRule()).isNotNull();
  }
}
