package com.verlumen.tradestream.strategies.configurable.llm;

import static org.junit.Assert.*;

import com.verlumen.tradestream.strategies.configurable.ConditionConfig;
import com.verlumen.tradestream.strategies.configurable.IndicatorConfig;
import com.verlumen.tradestream.strategies.configurable.ParameterDefinition;
import com.verlumen.tradestream.strategies.configurable.ParameterType;
import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import java.util.List;
import java.util.Map;
import org.junit.Test;

public class StrategySpecPromptTemplateTest {

  @Test
  public void getSystemPrompt_containsKeyInfo() {
    String prompt = StrategySpecPromptTemplate.getSystemPrompt();
    assertNotNull(prompt);
    assertTrue(prompt.contains("quantitative trading strategy"));
    assertTrue(prompt.contains("YAML"));
    assertTrue(prompt.contains("indicators"));
  }

  @Test
  public void buildUserPrompt_includesExamples() {
    StrategyConfig example = createSimpleConfig("TEST_STRATEGY");
    String prompt = StrategySpecPromptTemplate.buildUserPrompt(List.of(example), 0);

    assertNotNull(prompt);
    assertTrue(prompt.contains("TEST_STRATEGY"));
    assertTrue(prompt.contains("Few-Shot Examples"));
    assertTrue(prompt.contains("NOVEL"));
    assertTrue(prompt.contains("Creativity Hint"));
  }

  @Test
  public void buildUserPrompt_includesSchemaInfo() {
    StrategyConfig example = createSimpleConfig("TEST");
    String prompt = StrategySpecPromptTemplate.buildUserPrompt(List.of(example), 0);

    assertTrue(prompt.contains("CROSSED_UP"));
    assertTrue(prompt.contains("SMA"));
    assertTrue(prompt.contains("INTEGER"));
  }

  @Test
  public void creativityHints_cycleThroughAll() {
    int count = StrategySpecPromptTemplate.getCreativityHintCount();
    assertTrue(count > 0);

    // Each hint should be unique
    java.util.Set<String> hints = new java.util.HashSet<>();
    for (int i = 0; i < count; i++) {
      String hint = StrategySpecPromptTemplate.getCreativityHint(i);
      assertNotNull(hint);
      assertFalse(hint.isBlank());
      hints.add(hint);
    }
    assertEquals(count, hints.size());

    // Index wrapping should work
    assertEquals(
        StrategySpecPromptTemplate.getCreativityHint(0),
        StrategySpecPromptTemplate.getCreativityHint(count));
  }

  private StrategyConfig createSimpleConfig(String name) {
    return StrategyConfig.builder()
        .name(name)
        .description("Test strategy")
        .complexity("SIMPLE")
        .indicators(
            List.of(
                IndicatorConfig.builder()
                    .id("sma")
                    .type("SMA")
                    .input("close")
                    .params(Map.of("period", "${smaPeriod}"))
                    .build(),
                IndicatorConfig.builder()
                    .id("ema")
                    .type("EMA")
                    .input("close")
                    .params(Map.of("period", "${emaPeriod}"))
                    .build()))
        .entryConditions(
            List.of(
                ConditionConfig.builder()
                    .type("CROSSED_UP")
                    .indicator("sma")
                    .params(Map.of("crosses", "ema"))
                    .build()))
        .exitConditions(
            List.of(
                ConditionConfig.builder()
                    .type("CROSSED_DOWN")
                    .indicator("sma")
                    .params(Map.of("crosses", "ema"))
                    .build()))
        .parameters(
            List.of(
                ParameterDefinition.builder()
                    .name("smaPeriod")
                    .type(ParameterType.INTEGER)
                    .min(5)
                    .max(50)
                    .defaultValue(20)
                    .build(),
                ParameterDefinition.builder()
                    .name("emaPeriod")
                    .type(ParameterType.INTEGER)
                    .min(5)
                    .max(50)
                    .defaultValue(50)
                    .build()))
        .build();
  }
}
