package com.verlumen.tradestream.strategies.configurable.llm;

import static org.junit.Assert.*;

import com.verlumen.tradestream.strategies.configurable.ConditionConfig;
import com.verlumen.tradestream.strategies.configurable.IndicatorConfig;
import com.verlumen.tradestream.strategies.configurable.ParameterDefinition;
import com.verlumen.tradestream.strategies.configurable.ParameterType;
import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import java.util.List;
import java.util.Map;
import org.junit.Before;
import org.junit.Test;

public class GeneratedSpecValidatorTest {

  private GeneratedSpecValidator validator;

  @Before
  public void setUp() {
    validator = new GeneratedSpecValidator();
  }

  @Test
  public void validate_validConfig_passes() {
    StrategyConfig config = createValidConfig("TEST_VALID");
    GeneratedSpecValidator.ValidationReport report = validator.validate(config, List.of());

    assertTrue("Should be valid: " + report.getErrors(), report.isValid());
    assertTrue(report.isSyntaxValid());
    assertTrue(report.isLogicValid());
    assertTrue(report.isNovel());
  }

  @Test
  public void validate_nullConfig_fails() {
    GeneratedSpecValidator.ValidationReport report = validator.validate(null, List.of());
    assertFalse(report.isValid());
    assertFalse(report.isSyntaxValid());
  }

  @Test
  public void validate_missingName_fails() {
    StrategyConfig config = createValidConfig(null);
    config.setName(null);
    GeneratedSpecValidator.ValidationReport report = validator.validate(config, List.of());
    assertFalse(report.isSyntaxValid());
  }

  @Test
  public void validate_noIndicators_fails() {
    StrategyConfig config = createValidConfig("NO_IND");
    config.setIndicators(List.of());
    GeneratedSpecValidator.ValidationReport report = validator.validate(config, List.of());
    assertFalse(report.isSyntaxValid());
  }

  @Test
  public void validate_unknownIndicatorType_fails() {
    StrategyConfig config = createValidConfig("BAD_TYPE");
    config.setIndicators(
        List.of(
            IndicatorConfig.builder()
                .id("bad")
                .type("NONEXISTENT_INDICATOR")
                .input("close")
                .params(Map.of("period", "14"))
                .build()));
    GeneratedSpecValidator.ValidationReport report = validator.validate(config, List.of());
    assertFalse(report.isSyntaxValid());
    assertTrue(report.getErrors().stream().anyMatch(e -> e.contains("Unknown indicator type")));
  }

  @Test
  public void validate_unknownConditionType_fails() {
    StrategyConfig config = createValidConfig("BAD_COND");
    config.setEntryConditions(
        List.of(
            ConditionConfig.builder()
                .type("MADE_UP_CONDITION")
                .indicator("sma")
                .params(Map.of())
                .build()));
    GeneratedSpecValidator.ValidationReport report = validator.validate(config, List.of());
    assertFalse(report.isSyntaxValid());
  }

  @Test
  public void validate_undefinedParamReference_fails() {
    StrategyConfig config =
        StrategyConfig.builder()
            .name("BAD_PARAM_REF")
            .description("Test")
            .complexity("SIMPLE")
            .indicators(
                List.of(
                    IndicatorConfig.builder()
                        .id("sma")
                        .type("SMA")
                        .input("close")
                        .params(Map.of("period", "${nonExistentParam}"))
                        .build()))
            .entryConditions(
                List.of(
                    ConditionConfig.builder()
                        .type("IS_RISING")
                        .indicator("sma")
                        .params(Map.of("barCount", 1))
                        .build()))
            .exitConditions(
                List.of(
                    ConditionConfig.builder()
                        .type("IS_FALLING")
                        .indicator("sma")
                        .params(Map.of("barCount", 1))
                        .build()))
            .parameters(
                List.of(
                    ParameterDefinition.builder()
                        .name("otherParam")
                        .type(ParameterType.INTEGER)
                        .min(1)
                        .max(10)
                        .defaultValue(5)
                        .build()))
            .build();

    GeneratedSpecValidator.ValidationReport report = validator.validate(config, List.of());
    assertFalse(report.isLogicValid());
    assertTrue(report.getErrors().stream().anyMatch(e -> e.contains("nonExistentParam")));
  }

  @Test
  public void validate_conditionRefsUndefinedIndicator_fails() {
    StrategyConfig config = createValidConfig("BAD_IND_REF");
    config.setEntryConditions(
        List.of(
            ConditionConfig.builder()
                .type("CROSSED_UP")
                .indicator("doesNotExist")
                .params(Map.of("crosses", "ema"))
                .build()));

    GeneratedSpecValidator.ValidationReport report = validator.validate(config, List.of());
    assertFalse(report.isLogicValid());
  }

  @Test
  public void validate_paramMinGreaterThanMax_fails() {
    StrategyConfig config = createValidConfig("BAD_RANGE");
    config.setParameters(
        List.of(
            ParameterDefinition.builder()
                .name("param")
                .type(ParameterType.INTEGER)
                .min(100)
                .max(5)
                .defaultValue(50)
                .build()));

    GeneratedSpecValidator.ValidationReport report = validator.validate(config, List.of());
    assertFalse(report.isSyntaxValid());
    assertTrue(report.getErrors().stream().anyMatch(e -> e.contains("min > max")));
  }

  @Test
  public void validate_duplicateName_notNovel() {
    StrategyConfig existing = createValidConfig("EXISTING");
    StrategyConfig generated = createValidConfig("EXISTING");

    GeneratedSpecValidator.ValidationReport report =
        validator.validate(generated, List.of(existing));
    assertFalse(report.isNovel());
  }

  @Test
  public void validate_sameStructure_notNovel() {
    StrategyConfig existing = createValidConfig("ORIGINAL");
    StrategyConfig generated = createValidConfig("COPY_WITH_NEW_NAME");

    GeneratedSpecValidator.ValidationReport report =
        validator.validate(generated, List.of(existing));
    assertFalse(report.isNovel());
  }

  @Test
  public void validate_differentStructure_isNovel() {
    StrategyConfig existing = createValidConfig("ORIGINAL");
    StrategyConfig generated = createDifferentConfig("DIFFERENT");

    GeneratedSpecValidator.ValidationReport report =
        validator.validate(generated, List.of(existing));
    assertTrue(report.isNovel());
  }

  @Test
  public void parseYaml_validYaml_parses() {
    String yaml =
        "name: TEST\n"
            + "description: A test\n"
            + "complexity: SIMPLE\n"
            + "indicators:\n"
            + "  - id: sma\n"
            + "    type: SMA\n"
            + "    input: close\n"
            + "    params:\n"
            + "      period: \"14\"\n"
            + "entryConditions:\n"
            + "  - type: IS_RISING\n"
            + "    indicator: sma\n"
            + "    params:\n"
            + "      barCount: 1\n"
            + "exitConditions:\n"
            + "  - type: IS_FALLING\n"
            + "    indicator: sma\n"
            + "    params:\n"
            + "      barCount: 1\n"
            + "parameters:\n"
            + "  - name: period\n"
            + "    type: INTEGER\n"
            + "    min: 5\n"
            + "    max: 50\n"
            + "    defaultValue: 14\n";

    StrategyConfig config = validator.parseYaml(yaml);
    assertNotNull(config);
    assertEquals("TEST", config.getName());
  }

  @Test
  public void parseYaml_invalidYaml_returnsNull() {
    assertNull(validator.parseYaml("{{{{not yaml"));
  }

  @Test
  public void parseYaml_stripsCodeFences() {
    String yaml =
        "```yaml\n"
            + "name: TEST\n"
            + "description: A test\n"
            + "complexity: SIMPLE\n"
            + "indicators:\n"
            + "  - id: sma\n"
            + "    type: SMA\n"
            + "    input: close\n"
            + "    params:\n"
            + "      period: \"14\"\n"
            + "entryConditions:\n"
            + "  - type: IS_RISING\n"
            + "    indicator: sma\n"
            + "    params:\n"
            + "      barCount: 1\n"
            + "exitConditions:\n"
            + "  - type: IS_FALLING\n"
            + "    indicator: sma\n"
            + "    params:\n"
            + "      barCount: 1\n"
            + "parameters:\n"
            + "  - name: period\n"
            + "    type: INTEGER\n"
            + "    min: 5\n"
            + "    max: 50\n"
            + "    defaultValue: 14\n"
            + "```";

    StrategyConfig config = validator.parseYaml(yaml);
    assertNotNull(config);
    assertEquals("TEST", config.getName());
  }

  @Test
  public void validate_defaultOutsideRange_fails() {
    StrategyConfig config = createValidConfig("BAD_DEFAULT");
    config.setParameters(
        List.of(
            ParameterDefinition.builder()
                .name("param")
                .type(ParameterType.INTEGER)
                .min(5)
                .max(50)
                .defaultValue(100)
                .build()));

    GeneratedSpecValidator.ValidationReport report = validator.validate(config, List.of());
    assertFalse(report.isSyntaxValid());
    assertTrue(report.getErrors().stream().anyMatch(e -> e.contains("default outside")));
  }

  // --- Helper methods ---

  private StrategyConfig createValidConfig(String name) {
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

  private StrategyConfig createDifferentConfig(String name) {
    return StrategyConfig.builder()
        .name(name)
        .description("Different strategy")
        .complexity("MEDIUM")
        .indicators(
            List.of(
                IndicatorConfig.builder()
                    .id("rsi")
                    .type("RSI")
                    .input("close")
                    .params(Map.of("period", "${rsiPeriod}"))
                    .build(),
                IndicatorConfig.builder()
                    .id("adx")
                    .type("ADX")
                    .params(Map.of("period", "${adxPeriod}"))
                    .build()))
        .entryConditions(
            List.of(
                ConditionConfig.builder()
                    .type("UNDER_CONSTANT")
                    .indicator("rsi")
                    .params(Map.of("threshold", 30))
                    .build(),
                ConditionConfig.builder()
                    .type("OVER_CONSTANT")
                    .indicator("adx")
                    .params(Map.of("threshold", 20))
                    .build()))
        .exitConditions(
            List.of(
                ConditionConfig.builder()
                    .type("OVER_CONSTANT")
                    .indicator("rsi")
                    .params(Map.of("threshold", 70))
                    .build()))
        .parameters(
            List.of(
                ParameterDefinition.builder()
                    .name("rsiPeriod")
                    .type(ParameterType.INTEGER)
                    .min(7)
                    .max(21)
                    .defaultValue(14)
                    .build(),
                ParameterDefinition.builder()
                    .name("adxPeriod")
                    .type(ParameterType.INTEGER)
                    .min(10)
                    .max(30)
                    .defaultValue(14)
                    .build()))
        .build();
  }
}
