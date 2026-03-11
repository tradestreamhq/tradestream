package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import java.util.Map;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class IndicatorConfigTest {

  @Test
  public void builder_createsCorrectConfig() {
    IndicatorConfig config =
        IndicatorConfig.builder()
            .id("sma20")
            .type("SMA")
            .input("close")
            .params(Map.of("period", "20"))
            .build();

    assertEquals("sma20", config.getId());
    assertEquals("SMA", config.getType());
    assertEquals("close", config.getInput());
    assertEquals(Map.of("period", "20"), config.getParams());
  }

  @Test
  public void constructor_createsCorrectConfig() {
    Map<String, String> params = Map.of("period", "14");
    IndicatorConfig config = new IndicatorConfig("rsi14", "RSI", "close", params);

    assertEquals("rsi14", config.getId());
    assertEquals("RSI", config.getType());
    assertEquals("close", config.getInput());
    assertEquals(params, config.getParams());
  }

  @Test
  public void defaultConstructor_createsEmptyConfig() {
    IndicatorConfig config = new IndicatorConfig();
    assertNull(config.getId());
    assertNull(config.getType());
    assertNull(config.getInput());
    assertNull(config.getParams());
  }

  @Test
  public void setters_updateFields() {
    IndicatorConfig config = new IndicatorConfig();
    config.setId("ema50");
    config.setType("EMA");
    config.setInput("close");
    config.setParams(Map.of("period", "50"));

    assertEquals("ema50", config.getId());
    assertEquals("EMA", config.getType());
    assertEquals("close", config.getInput());
    assertEquals(Map.of("period", "50"), config.getParams());
  }

  @Test
  public void equals_sameValues_returnsTrue() {
    IndicatorConfig a = new IndicatorConfig("id", "SMA", "close", Map.of("period", "20"));
    IndicatorConfig b = new IndicatorConfig("id", "SMA", "close", Map.of("period", "20"));
    assertEquals(a, b);
    assertEquals(a.hashCode(), b.hashCode());
  }

  @Test
  public void equals_differentValues_returnsFalse() {
    IndicatorConfig a = new IndicatorConfig("id1", "SMA", "close", Map.of("period", "20"));
    IndicatorConfig b = new IndicatorConfig("id2", "SMA", "close", Map.of("period", "20"));
    assertNotEquals(a, b);
  }

  @Test
  public void equals_null_returnsFalse() {
    IndicatorConfig a = new IndicatorConfig("id", "SMA", "close", Map.of("period", "20"));
    assertNotEquals(a, null);
  }

  @Test
  public void equals_differentType_returnsFalse() {
    IndicatorConfig a = new IndicatorConfig("id", "SMA", "close", Map.of("period", "20"));
    IndicatorConfig b = new IndicatorConfig("id", "EMA", "close", Map.of("period", "20"));
    assertNotEquals(a, b);
  }

  @Test
  public void toString_containsFieldValues() {
    IndicatorConfig config = new IndicatorConfig("sma20", "SMA", "close", Map.of("period", "20"));
    String str = config.toString();
    assertTrue(str.contains("sma20"));
    assertTrue(str.contains("SMA"));
    assertTrue(str.contains("close"));
  }
}
