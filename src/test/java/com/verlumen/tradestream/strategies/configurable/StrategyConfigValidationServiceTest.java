package com.verlumen.tradestream.strategies.configurable;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class StrategyConfigValidationServiceTest {

  private StrategyConfigValidationService service;

  @Before
  public void setUp() {
    service = StrategyConfigValidationService.createDefault();
  }

  @Test
  public void validConfig_noErrors() {
    StrategyConfig config = buildValidConfig();
    List<ValidationResult> results = service.validate(config);
    long errorCount =
        results.stream().filter(r -> r.getSeverity() == ValidationResult.Severity.ERROR).count();
    assertEquals("Valid config should have no errors: " + results, 0, errorCount);
  }

  @Test
  public void missingName_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setName(null);
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("name")));
  }

  @Test
  public void missingDescription_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setDescription(null);
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("description")));
  }

  @Test
  public void emptyIndicators_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setIndicators(Collections.emptyList());
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("indicator")));
  }

  @Test
  public void emptyEntryConditions_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setEntryConditions(Collections.emptyList());
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("entry condition")));
  }

  @Test
  public void emptyExitConditions_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setExitConditions(Collections.emptyList());
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("exit condition")));
  }

  @Test
  public void invalidComplexity_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setComplexity("SUPER_COMPLEX");
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("complexity")));
  }

  @Test
  public void validComplexity_noComplexityError() {
    for (String complexity : List.of("SIMPLE", "MODERATE", "COMPLEX")) {
      StrategyConfig config = buildValidConfig();
      config.setComplexity(complexity);
      List<ValidationResult> results = service.validate(config);
      assertFalse(
          "Complexity '" + complexity + "' should not produce error",
          results.stream()
              .anyMatch(
                  r ->
                      r.getSeverity() == ValidationResult.Severity.ERROR
                          && r.getMessage().contains("complexity")));
    }
  }

  @Test
  public void duplicateParameterName_producesError() {
    StrategyConfig config = buildValidConfig();
    ParameterDefinition dup =
        new ParameterDefinition("smaPeriod", ParameterType.INTEGER, 5, 50, 14);
    config.setParameters(Arrays.asList(config.getParameters().get(0), dup));
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("Duplicate parameter")));
  }

  @Test
  public void paramMinGreaterThanMax_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setParameters(
        List.of(new ParameterDefinition("period", ParameterType.INTEGER, 50, 5, 10)));
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("min")
                        && r.getMessage().contains("max")));
  }

  @Test
  public void defaultBelowMin_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setParameters(
        List.of(new ParameterDefinition("period", ParameterType.INTEGER, 10, 50, 5)));
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("below min")));
  }

  @Test
  public void defaultAboveMax_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setParameters(
        List.of(new ParameterDefinition("period", ParameterType.INTEGER, 10, 50, 100)));
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("exceeds max")));
  }

  @Test
  public void unregisteredIndicatorType_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setIndicators(
        List.of(new IndicatorConfig("ind1", "NONEXISTENT_INDICATOR", "close", Map.of())));
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("unregistered type")));
  }

  @Test
  public void deprecatedIndicatorType_producesWarning() {
    StrategyConfig config = buildValidConfig();
    config.setIndicators(
        List.of(new IndicatorConfig("mom", "MOMENTUM", "close", Map.of("period", "${smaPeriod}"))));
    // Need to update conditions to reference existing indicator
    config.setEntryConditions(
        List.of(new ConditionConfig("CROSSED_UP", "mom", Map.of("value", 0.0))));
    config.setExitConditions(
        List.of(new ConditionConfig("CROSSED_DOWN", "mom", Map.of("value", 0.0))));
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.WARNING
                        && r.getMessage().contains("deprecated")));
  }

  @Test
  public void duplicateIndicatorId_producesError() {
    StrategyConfig config = buildValidConfig();
    IndicatorConfig ind1 =
        new IndicatorConfig("sma", "SMA", "close", Map.of("period", "${smaPeriod}"));
    IndicatorConfig ind2 =
        new IndicatorConfig("sma", "EMA", "close", Map.of("period", "${smaPeriod}"));
    config.setIndicators(Arrays.asList(ind1, ind2));
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("Duplicate indicator id")));
  }

  @Test
  public void unknownConditionType_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setEntryConditions(List.of(new ConditionConfig("NONEXISTENT_RULE", "sma", Map.of())));
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("Unknown")));
  }

  @Test
  public void conditionReferencesUndefinedIndicator_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setEntryConditions(
        List.of(new ConditionConfig("CROSSED_UP", "nonexistent", Map.of("value", 50.0))));
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("undefined indicator")));
  }

  @Test
  public void crossesParamReferencesUndefinedIndicator_producesError() {
    StrategyConfig config = buildValidConfig();
    config.setEntryConditions(
        List.of(new ConditionConfig("CROSSED_UP", "sma", Map.of("crosses", "nonexistent_signal"))));
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("crosses")
                        && r.getMessage().contains("undefined")));
  }

  @Test
  public void placeholderReferencesUndefinedParameter_producesError() {
    StrategyConfig config = buildValidConfig();
    config.getIndicators().get(0).setParams(Map.of("period", "${undefinedParam}"));
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.ERROR
                        && r.getMessage().contains("undefinedParam")));
  }

  @Test
  public void noParameters_producesWarning() {
    StrategyConfig config = buildValidConfig();
    config.setParameters(null);
    List<ValidationResult> results = service.validate(config);
    assertTrue(
        results.stream()
            .anyMatch(
                r ->
                    r.getSeverity() == ValidationResult.Severity.WARNING
                        && r.getMessage().contains("no parameters")));
  }

  @Test
  public void indicatorInputReferencesAnotherIndicator_noError() {
    StrategyConfig config = buildValidConfig();
    IndicatorConfig sma =
        new IndicatorConfig("sma", "SMA", "close", Map.of("period", "${smaPeriod}"));
    IndicatorConfig ema =
        new IndicatorConfig("ema", "EMA", "sma", Map.of("period", "${smaPeriod}"));
    config.setIndicators(Arrays.asList(sma, ema));
    config.setEntryConditions(
        List.of(new ConditionConfig("CROSSED_UP", "sma", Map.of("crosses", "ema"))));
    config.setExitConditions(
        List.of(new ConditionConfig("CROSSED_DOWN", "sma", Map.of("crosses", "ema"))));
    List<ValidationResult> results = service.validate(config);
    long errorCount =
        results.stream().filter(r -> r.getSeverity() == ValidationResult.Severity.ERROR).count();
    assertEquals("Config with chained indicators should be valid: " + results, 0, errorCount);
  }

  @Test
  public void validateAll_loadsAllStrategies() {
    List<ValidationResult> results = service.validateAll();
    // We should get results for all strategies (even if some have warnings)
    // The key test is that validateAll() doesn't throw
    assertFalse("validateAll should produce at least some results", results.isEmpty());
  }

  private StrategyConfig buildValidConfig() {
    IndicatorConfig indicator =
        new IndicatorConfig("sma", "SMA", "close", Map.of("period", "${smaPeriod}"));
    ConditionConfig entry = new ConditionConfig("CROSSED_UP", "sma", Map.of("value", 50.0));
    ConditionConfig exit = new ConditionConfig("CROSSED_DOWN", "sma", Map.of("value", 50.0));
    ParameterDefinition param =
        new ParameterDefinition("smaPeriod", ParameterType.INTEGER, 5, 50, 14);

    return new StrategyConfig(
        "TEST_STRATEGY",
        "A test strategy",
        "SIMPLE",
        "com.verlumen.tradestream.strategies.TestParameters",
        List.of(indicator),
        List.of(entry),
        List.of(exit),
        List.of(param));
  }
}
