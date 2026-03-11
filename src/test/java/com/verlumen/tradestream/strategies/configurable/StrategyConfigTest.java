package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.*;

import java.util.List;
import java.util.Map;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class StrategyConfigTest {

  @Test
  public void builder_createsCorrectConfig() {
    ParameterDefinition param = new ParameterDefinition("period", ParameterType.INTEGER, 5, 50, 20);
    IndicatorConfig indicator =
        new IndicatorConfig("sma", "SMA", "close", Map.of("period", "${period}"));
    ConditionConfig entry = new ConditionConfig("CROSSOVER", "sma", Map.of());
    ConditionConfig exit = new ConditionConfig("CROSSUNDER", "sma", Map.of());

    StrategyConfig config =
        StrategyConfig.builder()
            .name("test_strategy")
            .description("A test strategy")
            .complexity("SIMPLE")
            .parameterMessageType("TestParams")
            .indicators(List.of(indicator))
            .entryConditions(List.of(entry))
            .exitConditions(List.of(exit))
            .parameters(List.of(param))
            .build();

    assertEquals("test_strategy", config.getName());
    assertEquals("A test strategy", config.getDescription());
    assertEquals("SIMPLE", config.getComplexity());
    assertEquals("TestParams", config.getParameterMessageType());
    assertEquals(1, config.getIndicators().size());
    assertEquals(1, config.getEntryConditions().size());
    assertEquals(1, config.getExitConditions().size());
    assertEquals(1, config.getParameters().size());
  }

  @Test
  public void defaultConstructor_createsEmptyConfig() {
    StrategyConfig config = new StrategyConfig();
    assertNull(config.getName());
    assertNull(config.getDescription());
    assertNull(config.getComplexity());
    assertNull(config.getParameterMessageType());
    assertNull(config.getIndicators());
    assertNull(config.getEntryConditions());
    assertNull(config.getExitConditions());
    assertNull(config.getParameters());
  }

  @Test
  public void setters_updateFields() {
    StrategyConfig config = new StrategyConfig();
    config.setName("my_strategy");
    config.setDescription("desc");
    config.setComplexity("MEDIUM");
    config.setParameterMessageType("MyParams");
    config.setIndicators(List.of());
    config.setEntryConditions(List.of());
    config.setExitConditions(List.of());
    config.setParameters(List.of());

    assertEquals("my_strategy", config.getName());
    assertEquals("desc", config.getDescription());
    assertEquals("MEDIUM", config.getComplexity());
    assertEquals("MyParams", config.getParameterMessageType());
    assertEquals(0, config.getIndicators().size());
    assertEquals(0, config.getEntryConditions().size());
    assertEquals(0, config.getExitConditions().size());
    assertEquals(0, config.getParameters().size());
  }

  @Test
  public void equals_sameValues_returnsTrue() {
    StrategyConfig a =
        StrategyConfig.builder()
            .name("test")
            .description("desc")
            .complexity("SIMPLE")
            .parameterMessageType("Params")
            .indicators(List.of())
            .entryConditions(List.of())
            .exitConditions(List.of())
            .parameters(List.of())
            .build();

    StrategyConfig b =
        StrategyConfig.builder()
            .name("test")
            .description("desc")
            .complexity("SIMPLE")
            .parameterMessageType("Params")
            .indicators(List.of())
            .entryConditions(List.of())
            .exitConditions(List.of())
            .parameters(List.of())
            .build();

    assertEquals(a, b);
    assertEquals(a.hashCode(), b.hashCode());
  }

  @Test
  public void equals_differentName_returnsFalse() {
    StrategyConfig a = StrategyConfig.builder().name("test1").indicators(List.of()).build();
    StrategyConfig b = StrategyConfig.builder().name("test2").indicators(List.of()).build();
    assertNotEquals(a, b);
  }

  @Test
  public void equals_null_returnsFalse() {
    StrategyConfig a = StrategyConfig.builder().name("test").build();
    assertNotEquals(a, null);
  }

  @Test
  public void toString_containsFieldValues() {
    StrategyConfig config =
        StrategyConfig.builder()
            .name("my_strategy")
            .description("A strategy")
            .complexity("SIMPLE")
            .build();
    String str = config.toString();
    assertTrue(str.contains("my_strategy"));
    assertTrue(str.contains("A strategy"));
    assertTrue(str.contains("SIMPLE"));
  }
}
