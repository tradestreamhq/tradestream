package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import java.util.Map;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class ConditionConfigTest {

  @Test
  public void builder_createsCorrectConfig() {
    ConditionConfig config =
        ConditionConfig.builder()
            .type("CROSSOVER")
            .indicator("ema")
            .params(Map.of("period", 14))
            .build();

    assertEquals("CROSSOVER", config.getType());
    assertEquals("ema", config.getIndicator());
    assertEquals(Map.of("period", 14), config.getParams());
  }

  @Test
  public void constructor_createsCorrectConfig() {
    Map<String, Object> params = Map.of("threshold", 30.0);
    ConditionConfig config = new ConditionConfig("OVER", "rsi", params);

    assertEquals("OVER", config.getType());
    assertEquals("rsi", config.getIndicator());
    assertEquals(params, config.getParams());
  }

  @Test
  public void defaultConstructor_createsEmptyConfig() {
    ConditionConfig config = new ConditionConfig();
    assertNull(config.getType());
    assertNull(config.getIndicator());
    assertNull(config.getParams());
  }

  @Test
  public void setters_updateFields() {
    ConditionConfig config = new ConditionConfig();
    config.setType("UNDER");
    config.setIndicator("sma");
    config.setParams(Map.of("period", 20));

    assertEquals("UNDER", config.getType());
    assertEquals("sma", config.getIndicator());
    assertEquals(Map.of("period", 20), config.getParams());
  }

  @Test
  public void equals_sameValues_returnsTrue() {
    ConditionConfig a = new ConditionConfig("CROSSOVER", "ema", Map.of("period", 14));
    ConditionConfig b = new ConditionConfig("CROSSOVER", "ema", Map.of("period", 14));
    assertEquals(a, b);
    assertEquals(a.hashCode(), b.hashCode());
  }

  @Test
  public void equals_differentValues_returnsFalse() {
    ConditionConfig a = new ConditionConfig("CROSSOVER", "ema", Map.of("period", 14));
    ConditionConfig b = new ConditionConfig("UNDER", "ema", Map.of("period", 14));
    assertNotEquals(a, b);
  }

  @Test
  public void equals_null_returnsFalse() {
    ConditionConfig a = new ConditionConfig("CROSSOVER", "ema", Map.of("period", 14));
    assertNotEquals(a, null);
  }

  @Test
  public void equals_differentIndicator_returnsFalse() {
    ConditionConfig a = new ConditionConfig("CROSSOVER", "ema", Map.of("period", 14));
    ConditionConfig b = new ConditionConfig("CROSSOVER", "sma", Map.of("period", 14));
    assertNotEquals(a, b);
  }

  @Test
  public void toString_containsFieldValues() {
    ConditionConfig config = new ConditionConfig("CROSSOVER", "ema", Map.of("period", 14));
    String str = config.toString();
    assertTrue(str.contains("CROSSOVER"));
    assertTrue(str.contains("ema"));
  }
}
