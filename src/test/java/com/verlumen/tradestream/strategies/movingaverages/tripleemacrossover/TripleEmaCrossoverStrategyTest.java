package com.verlumen.tradestream.strategies.movingaverages.tripleemacrossover;

import static org.junit.jupiter.api.Assertions.assertEquals;
import com.verlumen.tradestream.strategies.TripleEmaCrossoverParameters;
import org.junit.jupiter.api.Test;

class TripleEmaCrossoverStrategyTest {
  @Test
  void getDefaultParameters_shouldReturnDefinedDefaults() {
    TripleEmaCrossoverParamConfig paramConfig = new TripleEmaCrossoverParamConfig();
    TripleEmaCrossoverParameters params = paramConfig.getDefaultParameters();
    assertEquals(5, params.getShortEmaPeriod()); // Example
    assertEquals(10, params.getMediumEmaPeriod()); // Example
    assertEquals(20, params.getLongEmaPeriod());  // Example
  }
}
