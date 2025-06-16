package com.verlumen.tradestream.strategies.movingaverages.momentumsmarrossover;

import static org.junit.jupiter.api.Assertions.assertEquals;
import com.verlumen.tradestream.strategies.MomentumSmaCrossoverParameters;
import org.junit.jupiter.api.Test;

class MomentumSmaCrossoverStrategyTest {
  @Test
  void getDefaultParameters_shouldReturnDefinedDefaults() {
    MomentumSmaCrossoverParamConfig paramConfig = new MomentumSmaCrossoverParamConfig();
    MomentumSmaCrossoverParameters params = paramConfig.getDefaultParameters();
    assertEquals(14, params.getMomentumPeriod()); // Example default
    assertEquals(9, params.getSmaPeriod());  // Example default
  }
}
