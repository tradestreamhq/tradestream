package com.verlumen.tradestream.strategies.movingaverages.doubleemacrossover;

import static org.junit.jupiter.api.Assertions.assertEquals;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import org.junit.jupiter.api.Test;

class DoubleEmaCrossoverStrategyTest {
  @Test
  void getDefaultParameters_shouldReturnDefinedDefaults() {
    DoubleEmaCrossoverParamConfig paramConfig = new DoubleEmaCrossoverParamConfig();
    DoubleEmaCrossoverParameters params = paramConfig.getDefaultParameters();
    assertEquals(10, params.getShortEmaPeriod()); // Example default
    assertEquals(20, params.getLongEmaPeriod());  // Example default
  }
}
