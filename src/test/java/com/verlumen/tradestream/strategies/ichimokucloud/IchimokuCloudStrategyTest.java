package com.verlumen.tradestream.strategies.ichimokucloud;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.verlumen.tradestream.strategies.IchimokuCloudParameters;
import org.junit.jupiter.api.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;

class IchimokuCloudStrategyTest {
  @Test
  void getDefaultParameters_shouldReturnDefinedDefaults() {
    IchimokuCloudParamConfig paramConfig = new IchimokuCloudParamConfig();
    IchimokuCloudParameters params = paramConfig.getDefaultParameters();
    assertEquals(9, params.getTenkanSenPeriod()); // Example
    assertEquals(26, params.getKijunSenPeriod());  // Example
    assertEquals(52, params.getSenkouSpanBPeriod()); // Example
    assertEquals(26, params.getChikouSpanPeriod()); // Example
  }

  @Test
  void strategyFactory_getDefaultParameters_shouldReturnDefaults() {
      IchimokuCloudStrategyFactory factory = new IchimokuCloudStrategyFactory();
      IchimokuCloudParameters params = factory.getDefaultParameters();
      assertNotNull(params);
      assertEquals(9, params.getTenkanSenPeriod());
      assertEquals(26, params.getKijunSenPeriod());
      assertEquals(52, params.getSenkouSpanBPeriod());
      assertEquals(26, params.getChikouSpanPeriod());
  }

  @Test
  void strategyFactory_createStrategy_shouldThrowUntilImplemented() {
      IchimokuCloudStrategyFactory factory = new IchimokuCloudStrategyFactory();
      IchimokuCloudParameters params = factory.getDefaultParameters();
      BarSeries series = new BaseBarSeries(); // Dummy series
      assertThrows(UnsupportedOperationException.class, () -> {
          factory.createStrategy(series, params);
      });
  }
}
