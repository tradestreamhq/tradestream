package com.verlumen.tradestream.strategies.configurable;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Validates YAML strategy configurations against their Java implementations. Checks for structural
 * correctness, parameter validity, indicator registration, condition types, and deprecated configs.
 */
public final class StrategyConfigValidationService {
  private static final Pattern PLACEHOLDER_PATTERN = Pattern.compile("\\$\\{([^}]+)}");
  private static final Set<String> VALID_COMPLEXITIES = Set.of("SIMPLE", "MODERATE", "COMPLEX");
  private static final Set<String> VALID_INPUTS =
      Set.of("close", "open", "high", "low", "volume", "typical_price", "median_price");
  private static final Set<String> DEPRECATED_INDICATOR_TYPES = Set.of("MOMENTUM");

  private final IndicatorRegistry indicatorRegistry;
  private final RuleRegistry ruleRegistry;

  public StrategyConfigValidationService(
      IndicatorRegistry indicatorRegistry, RuleRegistry ruleRegistry) {
    this.indicatorRegistry = indicatorRegistry;
    this.ruleRegistry = ruleRegistry;
  }

  public static StrategyConfigValidationService createDefault() {
    return new StrategyConfigValidationService(
        IndicatorRegistry.defaultRegistry(), RuleRegistry.defaultRegistry());
  }

  /** Validates a single strategy configuration. */
  public List<ValidationResult> validate(StrategyConfig config) {
    List<ValidationResult> results = new ArrayList<>();
    String name = config.getName() != null ? config.getName() : "<unnamed>";

    validateRequiredFields(config, name, results);
    validateComplexity(config, name, results);
    validateParameters(config, name, results);

    Set<String> definedIndicatorIds = validateIndicators(config, name, results);
    Set<String> definedParamNames = collectParameterNames(config);

    validateConditions(config.getEntryConditions(), "entry", name, definedIndicatorIds, results);
    validateConditions(config.getExitConditions(), "exit", name, definedIndicatorIds, results);
    validatePlaceholderReferences(config, name, definedParamNames, results);

    return results;
  }

  /** Validates all registered ConfigStrategy configs. */
  public List<ValidationResult> validateAll() {
    List<ValidationResult> results = new ArrayList<>();
    for (StrategyConfigLoader.ConfigStrategy strategy :
        StrategyConfigLoader.ConfigStrategy.values()) {
      try {
        StrategyConfig config = strategy.get();
        results.addAll(validate(config));
      } catch (Exception e) {
        results.add(ValidationResult.error(strategy.name(), "Failed to load config: " + e.getMessage()));
      }
    }
    return results;
  }

  private void validateRequiredFields(
      StrategyConfig config, String name, List<ValidationResult> results) {
    if (config.getName() == null || config.getName().isEmpty()) {
      results.add(ValidationResult.error(name, "Missing required field: name"));
    }
    if (config.getDescription() == null || config.getDescription().isEmpty()) {
      results.add(ValidationResult.error(name, "Missing required field: description"));
    }
    if (config.getIndicators() == null || config.getIndicators().isEmpty()) {
      results.add(ValidationResult.error(name, "Strategy must define at least one indicator"));
    }
    if (config.getEntryConditions() == null || config.getEntryConditions().isEmpty()) {
      results.add(
          ValidationResult.error(name, "Strategy must define at least one entry condition"));
    }
    if (config.getExitConditions() == null || config.getExitConditions().isEmpty()) {
      results.add(ValidationResult.error(name, "Strategy must define at least one exit condition"));
    }
    if (config.getParameters() == null || config.getParameters().isEmpty()) {
      results.add(
          ValidationResult.warning(name, "Strategy defines no parameters (not optimizable)"));
    }
  }

  private void validateComplexity(
      StrategyConfig config, String name, List<ValidationResult> results) {
    if (config.getComplexity() != null
        && !VALID_COMPLEXITIES.contains(config.getComplexity().toUpperCase())) {
      results.add(
          ValidationResult.error(
              name,
              "Invalid complexity '"
                  + config.getComplexity()
                  + "'. Must be one of: "
                  + VALID_COMPLEXITIES));
    }
  }

  private void validateParameters(
      StrategyConfig config, String name, List<ValidationResult> results) {
    if (config.getParameters() == null) {
      return;
    }

    Set<String> seenNames = new HashSet<>();
    for (ParameterDefinition param : config.getParameters()) {
      if (param.getName() == null || param.getName().isEmpty()) {
        results.add(ValidationResult.error(name, "Parameter has no name"));
        continue;
      }

      if (!seenNames.add(param.getName())) {
        results.add(ValidationResult.error(name, "Duplicate parameter name: " + param.getName()));
      }

      if (param.getType() == null) {
        results.add(ValidationResult.error(name, "Parameter '" + param.getName() + "' has no type"));
      }

      if (param.getMin() != null && param.getMax() != null) {
        if (param.getMin().doubleValue() > param.getMax().doubleValue()) {
          results.add(
              ValidationResult.error(
                  name,
                  "Parameter '"
                      + param.getName()
                      + "' has min ("
                      + param.getMin()
                      + ") > max ("
                      + param.getMax()
                      + ")"));
        }
      }

      if (param.getDefaultValue() != null) {
        double defaultVal = param.getDefaultValue().doubleValue();
        if (param.getMin() != null && defaultVal < param.getMin().doubleValue()) {
          results.add(
              ValidationResult.error(
                  name,
                  "Parameter '"
                      + param.getName()
                      + "' default ("
                      + param.getDefaultValue()
                      + ") is below min ("
                      + param.getMin()
                      + ")"));
        }
        if (param.getMax() != null && defaultVal > param.getMax().doubleValue()) {
          results.add(
              ValidationResult.error(
                  name,
                  "Parameter '"
                      + param.getName()
                      + "' default ("
                      + param.getDefaultValue()
                      + ") exceeds max ("
                      + param.getMax()
                      + ")"));
        }
      }

      if (param.getType() == ParameterType.INTEGER && param.getDefaultValue() != null) {
        double val = param.getDefaultValue().doubleValue();
        if (val != Math.floor(val)) {
          results.add(
              ValidationResult.warning(
                  name,
                  "Parameter '"
                      + param.getName()
                      + "' is INTEGER but default is not a whole number: "
                      + param.getDefaultValue()));
        }
      }
    }
  }

  private Set<String> validateIndicators(
      StrategyConfig config, String name, List<ValidationResult> results) {
    Set<String> definedIds = new HashSet<>();
    if (config.getIndicators() == null) {
      return definedIds;
    }

    for (IndicatorConfig indicator : config.getIndicators()) {
      if (indicator.getId() == null || indicator.getId().isEmpty()) {
        results.add(ValidationResult.error(name, "Indicator has no id"));
        continue;
      }

      if (!definedIds.add(indicator.getId())) {
        results.add(ValidationResult.error(name, "Duplicate indicator id: " + indicator.getId()));
      }

      if (indicator.getType() == null || indicator.getType().isEmpty()) {
        results.add(ValidationResult.error(name, "Indicator '" + indicator.getId() + "' has no type"));
      } else if (!indicatorRegistry.hasIndicator(indicator.getType())) {
        results.add(
            ValidationResult.error(
                name,
                "Indicator '"
                    + indicator.getId()
                    + "' uses unregistered type: "
                    + indicator.getType()));
      }

      if (indicator.getType() != null
          && DEPRECATED_INDICATOR_TYPES.contains(indicator.getType().toUpperCase())) {
        results.add(
            ValidationResult.warning(
                name,
                "Indicator '"
                    + indicator.getId()
                    + "' uses deprecated type: "
                    + indicator.getType()
                    + ". Consider using ROC instead."));
      }

      if (indicator.getInput() != null
          && !VALID_INPUTS.contains(indicator.getInput().toLowerCase())
          && !definedIds.contains(indicator.getInput())) {
        // Input could reference a previously defined indicator id - only warn if not found
        boolean foundLater = false;
        if (config.getIndicators() != null) {
          for (IndicatorConfig other : config.getIndicators()) {
            if (indicator.getInput().equals(other.getId())) {
              foundLater = true;
              break;
            }
          }
        }
        if (!foundLater) {
          results.add(
              ValidationResult.error(
                  name,
                  "Indicator '"
                      + indicator.getId()
                      + "' references unknown input: "
                      + indicator.getInput()));
        }
      }
    }
    return definedIds;
  }

  private void validateConditions(
      List<ConditionConfig> conditions,
      String conditionType,
      String name,
      Set<String> definedIndicatorIds,
      List<ValidationResult> results) {
    if (conditions == null) {
      return;
    }

    for (ConditionConfig condition : conditions) {
      if (condition.getType() == null || condition.getType().isEmpty()) {
        results.add(ValidationResult.error(name, "An " + conditionType + " condition has no type"));
        continue;
      }

      if (!ruleRegistry.hasRule(condition.getType())) {
        results.add(
            ValidationResult.error(name, "Unknown " + conditionType + " condition type: " + condition.getType()));
      }

      if (condition.getIndicator() != null
          && !definedIndicatorIds.contains(condition.getIndicator())) {
        results.add(
            ValidationResult.error(
                name,
                "Condition type '"
                    + condition.getType()
                    + "' references undefined indicator: "
                    + condition.getIndicator()));
      }

      // Check that cross-reference params (like "crosses") refer to defined indicators
      if (condition.getParams() != null) {
        Object crossesRef = condition.getParams().get("crosses");
        if (crossesRef instanceof String && !definedIndicatorIds.contains((String) crossesRef)) {
          results.add(
              ValidationResult.error(
                  name, "Condition param 'crosses' references undefined indicator: " + crossesRef));
        }
        Object otherRef = condition.getParams().get("other");
        if (otherRef instanceof String && !definedIndicatorIds.contains((String) otherRef)) {
          results.add(
              ValidationResult.error(
                  name, "Condition param 'other' references undefined indicator: " + otherRef));
        }
      }
    }
  }

  private void validatePlaceholderReferences(
      StrategyConfig config,
      String name,
      Set<String> definedParamNames,
      List<ValidationResult> results) {
    if (config.getIndicators() == null) {
      return;
    }
    for (IndicatorConfig indicator : config.getIndicators()) {
      if (indicator.getParams() == null) {
        continue;
      }
      for (Map.Entry<String, String> entry : indicator.getParams().entrySet()) {
        java.util.regex.Matcher matcher = PLACEHOLDER_PATTERN.matcher(entry.getValue());
        while (matcher.find()) {
          String paramRef = matcher.group(1);
          if (!definedParamNames.contains(paramRef)) {
            results.add(
                ValidationResult.error(
                    name,
                    "Indicator '"
                        + indicator.getId()
                        + "' param '"
                        + entry.getKey()
                        + "' references undefined parameter: ${"
                        + paramRef
                        + "}"));
          }
        }
      }
    }
  }

  private Set<String> collectParameterNames(StrategyConfig config) {
    Set<String> names = new HashSet<>();
    if (config.getParameters() != null) {
      for (ParameterDefinition param : config.getParameters()) {
        if (param.getName() != null) {
          names.add(param.getName());
        }
      }
    }
    return names;
  }
}
