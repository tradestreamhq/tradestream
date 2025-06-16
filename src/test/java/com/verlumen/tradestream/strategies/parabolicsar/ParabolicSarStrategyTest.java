package com.verlumen.tradestream.strategies.parabolicsar;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.verlumen.tradestream.strategies.ParabolicSarParameters;
import org.junit.jupiter.api.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;

class ParabolicSarStrategyTest {
  @Test
  void getDefaultParameters_shouldReturnDefinedDefaults() {
    ParabolicSarParamConfig paramConfig = new ParabolicSarParamConfig();
    ParabolicSarParameters params = paramConfig.getDefaultParameters();
    assertEquals(0.02, params.getAccelerationFactorStart(), 0.001); // Example
    assertEquals(0.02, params.getAccelerationFactorIncrement(), 0.001);  // Example
    assertEquals(0.2, params.getAccelerationFactorMax(), 0.001); // Example
  }

  @Test
  void strategyFactory_getDefaultParameters_shouldReturnDefaults() {
      ParabolicSarStrategyFactory factory = new ParabolicSarStrategyFactory();
      ParabolicSarParameters params = factory.getDefaultParameters();
      assertNotNull(params);
      assertEquals(0.02, params.getAccelerationFactorStart(), 0.001);
      assertEquals(0.02, params.getAccelerationFactorIncrement(), 0.001);
      assertEquals(0.2, params.getAccelerationFactorMax(), 0.001);
  }

  @Test
  void strategyFactory_createStrategy_shouldThrowUntilImplemented() {
      ParabolicSarStrategyFactory factory = new ParabolicSarStrategyFactory();
      ParabolicSarParameters params = factory.getDefaultParameters();
      BarSeries series = new BaseBarSeries(); // Dummy series
      assertThrows(UnsupportedOperationException.class, () -> {
          factory.createStrategy(series, params);
      });
  }
}
