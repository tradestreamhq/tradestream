package com.verlumen.tradestream.strategies.aroonmfi;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.verlumen.tradestream.strategies.AroonMfiParameters;
import org.junit.jupiter.api.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;

class AroonMfiStrategyTest {
  @Test
  void getDefaultParameters_shouldReturnDefinedDefaults() {
    AroonMfiParamConfig paramConfig = new AroonMfiParamConfig();
    AroonMfiParameters params = paramConfig.getDefaultParameters();
    assertEquals(25, params.getAroonPeriod()); // Example
    assertEquals(14, params.getMfiPeriod());  // Example
    assertEquals(80, params.getOverboughtThreshold()); // Example
    assertEquals(20, params.getOversoldThreshold()); // Example
  }

  @Test
  void strategyFactory_getDefaultParameters_shouldReturnDefaults() {
      AroonMfiStrategyFactory factory = new AroonMfiStrategyFactory();
      AroonMfiParameters params = factory.getDefaultParameters();
      assertNotNull(params);
      assertEquals(25, params.getAroonPeriod());
      assertEquals(14, params.getMfiPeriod());
      assertEquals(80, params.getOverboughtThreshold());
      assertEquals(20, params.getOversoldThreshold());
  }

  @Test
  void strategyFactory_createStrategy_shouldThrowUntilImplemented() {
      AroonMfiStrategyFactory factory = new AroonMfiStrategyFactory();
      AroonMfiParameters params = factory.getDefaultParameters();
      BarSeries series = new BaseBarSeries(); // Dummy series
      assertThrows(UnsupportedOperationException.class, () -> {
          factory.createStrategy(series, params);
      });
  }
}
