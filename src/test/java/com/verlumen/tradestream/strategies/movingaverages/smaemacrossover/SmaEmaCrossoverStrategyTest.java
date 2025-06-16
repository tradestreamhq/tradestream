package com.verlumen.tradestream.strategies.movingaverages.smaemacrossover;

import static org.junit.jupiter.api.Assertions.assertEquals;
import com.verlumen.tradestream.strategies.SmaEmaCrossoverParameters;
import org.junit.jupiter.api.Test;

class SmaEmaCrossoverStrategyTest {
  @Test
  void getDefaultParameters_shouldReturnDefinedDefaults() {
    SmaEmaCrossoverParamConfig paramConfig = new SmaEmaCrossoverParamConfig();
    SmaEmaCrossoverParameters params = paramConfig.getDefaultParameters();
    assertEquals(50, params.getSmaPeriod()); // Example default
    assertEquals(20, params.getEmaPeriod());  // Example default
  }
}
