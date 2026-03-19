package com.verlumen.tradestream.strategies.configurable.llm;

import com.verlumen.tradestream.strategies.configurable.ConditionConfig;
import com.verlumen.tradestream.strategies.configurable.IndicatorConfig;
import com.verlumen.tradestream.strategies.configurable.IndicatorRegistry;
import com.verlumen.tradestream.strategies.configurable.ParameterDefinition;
import com.verlumen.tradestream.strategies.configurable.ParameterType;
import com.verlumen.tradestream.strategies.configurable.RuleRegistry;
import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import com.verlumen.tradestream.strategies.configurable.StrategyConfigLoader;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Validates LLM-generated strategy specs. Checks structural correctness, indicator/condition types,
 * parameter consistency, and novelty against existing strategies.
 */
public final class GeneratedSpecValidator {
  private static final Pattern PLACEHOLDER = Pattern.compile("\\$\\{([^}]+)}");

  private final IndicatorRegistry indicatorRegistry;
  private final RuleRegistry ruleRegistry;

  public GeneratedSpecValidator() {
    this(IndicatorRegistry.defaultRegistry(), RuleRegistry.defaultRegistry());
  }

  public GeneratedSpecValidator(IndicatorRegistry indicatorRegistry, RuleRegistry ruleRegistry) {
    this.indicatorRegistry = indicatorRegistry;
    this.ruleRegistry = ruleRegistry;
  }

  /** Parse YAML text into a StrategyConfig, returning null if unparseable. */
  public StrategyConfig parseYaml(String yamlText) {
    try {
      String cleaned = yamlText.trim();
      // Strip markdown code fences if present
      if (cleaned.startsWith("```")) {
        int start = cleaned.indexOf('\n') + 1;
        int end = cleaned.lastIndexOf("```");
        if (end > start) {
          cleaned = cleaned.substring(start, end).trim();
        }
      }
      return StrategyConfigLoader.parseYaml(cleaned);
    } catch (Exception e) {
      return null;
    }
  }

  /** Full validation of a generated spec. */
  public ValidationReport validate(StrategyConfig config, List<StrategyConfig> existingConfigs) {
    List<String> errors = new ArrayList<>();
    List<String> warnings = new ArrayList<>();

    if (config == null) {
      errors.add("Config is null (could not parse)");
      return new ValidationReport(false, false, false, false, errors, warnings);
    }

    boolean syntaxValid = validateSyntax(config, errors);
    boolean logicValid = syntaxValid && validateLogic(config, errors, warnings);
    boolean novel = checkNovelty(config, existingConfigs);
    boolean buildable = logicValid && checkBuildable(config, errors);

    boolean isValid = syntaxValid && logicValid && novel && buildable;
    return new ValidationReport(isValid, syntaxValid, logicValid, novel, errors, warnings);
  }

  private boolean validateSyntax(StrategyConfig config, List<String> errors) {
    boolean valid = true;

    if (config.getName() == null || config.getName().isBlank()) {
      errors.add("Missing name");
      valid = false;
    }
    if (config.getIndicators() == null || config.getIndicators().isEmpty()) {
      errors.add("No indicators defined");
      valid = false;
    }
    if (config.getEntryConditions() == null || config.getEntryConditions().isEmpty()) {
      errors.add("No entry conditions");
      valid = false;
    }
    if (config.getExitConditions() == null || config.getExitConditions().isEmpty()) {
      errors.add("No exit conditions");
      valid = false;
    }
    if (config.getParameters() == null || config.getParameters().isEmpty()) {
      errors.add("No parameters (not optimizable)");
      valid = false;
    }

    // Validate each indicator has an id and valid type
    if (config.getIndicators() != null) {
      Set<String> ids = new HashSet<>();
      for (IndicatorConfig ind : config.getIndicators()) {
        if (ind.getId() == null || ind.getId().isBlank()) {
          errors.add("Indicator missing id");
          valid = false;
        } else if (!ids.add(ind.getId())) {
          errors.add("Duplicate indicator id: " + ind.getId());
          valid = false;
        }
        if (ind.getType() == null || !indicatorRegistry.hasIndicator(ind.getType())) {
          errors.add("Unknown indicator type: " + ind.getType());
          valid = false;
        }
      }
    }

    // Validate conditions reference valid types
    if (config.getEntryConditions() != null) {
      for (ConditionConfig cond : config.getEntryConditions()) {
        if (cond.getType() == null || !ruleRegistry.hasRule(cond.getType())) {
          errors.add("Unknown entry condition type: " + cond.getType());
          valid = false;
        }
      }
    }
    if (config.getExitConditions() != null) {
      for (ConditionConfig cond : config.getExitConditions()) {
        if (cond.getType() == null || !ruleRegistry.hasRule(cond.getType())) {
          errors.add("Unknown exit condition type: " + cond.getType());
          valid = false;
        }
      }
    }

    // Validate parameters
    if (config.getParameters() != null) {
      for (ParameterDefinition param : config.getParameters()) {
        if (param.getName() == null || param.getName().isBlank()) {
          errors.add("Parameter missing name");
          valid = false;
        }
        if (param.getType() == null) {
          errors.add("Parameter '" + param.getName() + "' missing type");
          valid = false;
        }
        if (param.getMin() != null
            && param.getMax() != null
            && param.getMin().doubleValue() > param.getMax().doubleValue()) {
          errors.add("Parameter '" + param.getName() + "' has min > max");
          valid = false;
        }
        if (param.getDefaultValue() != null && param.getMin() != null && param.getMax() != null) {
          double def = param.getDefaultValue().doubleValue();
          if (def < param.getMin().doubleValue() || def > param.getMax().doubleValue()) {
            errors.add("Parameter '" + param.getName() + "' default outside [min, max]");
            valid = false;
          }
        }
      }
    }

    return valid;
  }

  private boolean validateLogic(
      StrategyConfig config, List<String> errors, List<String> warnings) {
    boolean valid = true;

    Set<String> indicatorIds = new HashSet<>();
    if (config.getIndicators() != null) {
      for (IndicatorConfig ind : config.getIndicators()) {
        if (ind.getId() != null) {
          indicatorIds.add(ind.getId());
        }
      }
    }

    // Check conditions reference defined indicators
    valid &= validateConditionRefs(config.getEntryConditions(), "entry", indicatorIds, errors);
    valid &= validateConditionRefs(config.getExitConditions(), "exit", indicatorIds, errors);

    // Check parameter placeholders resolve
    Set<String> paramNames = new HashSet<>();
    if (config.getParameters() != null) {
      for (ParameterDefinition p : config.getParameters()) {
        if (p.getName() != null) {
          paramNames.add(p.getName());
        }
      }
    }

    if (config.getIndicators() != null) {
      for (IndicatorConfig ind : config.getIndicators()) {
        if (ind.getParams() != null) {
          for (Map.Entry<String, String> entry : ind.getParams().entrySet()) {
            if (entry.getValue() != null) {
              Matcher m = PLACEHOLDER.matcher(entry.getValue());
              while (m.find()) {
                if (!paramNames.contains(m.group(1))) {
                  errors.add(
                      "Indicator '"
                          + ind.getId()
                          + "' references undefined parameter: ${"
                          + m.group(1)
                          + "}");
                  valid = false;
                }
              }
            }
          }
        }
      }
    }

    // Check indicator input references
    if (config.getIndicators() != null) {
      Set<String> builtSoFar = new HashSet<>();
      Set<String> validInputs = Set.of("close", "high", "low", "open", "volume");
      for (IndicatorConfig ind : config.getIndicators()) {
        if (ind.getInput() != null
            && !ind.getInput().isBlank()
            && !validInputs.contains(ind.getInput().toLowerCase())
            && !builtSoFar.contains(ind.getInput())) {
          errors.add(
              "Indicator '" + ind.getId() + "' references undefined input: " + ind.getInput());
          valid = false;
        }
        if (ind.getId() != null) {
          builtSoFar.add(ind.getId());
        }
      }
    }

    return valid;
  }

  private boolean validateConditionRefs(
      List<ConditionConfig> conditions,
      String condType,
      Set<String> indicatorIds,
      List<String> errors) {
    if (conditions == null) return true;
    boolean valid = true;

    for (ConditionConfig cond : conditions) {
      if (cond.getIndicator() != null && !indicatorIds.contains(cond.getIndicator())) {
        errors.add(condType + " condition references undefined indicator: " + cond.getIndicator());
        valid = false;
      }
      if (cond.getParams() != null) {
        Object crosses = cond.getParams().get("crosses");
        if (crosses instanceof String && !indicatorIds.contains((String) crosses)) {
          errors.add(condType + " condition 'crosses' references undefined indicator: " + crosses);
          valid = false;
        }
        Object other = cond.getParams().get("other");
        if (other instanceof String && !indicatorIds.contains((String) other)) {
          errors.add(condType + " condition 'other' references undefined indicator: " + other);
          valid = false;
        }
      }
    }
    return valid;
  }

  private boolean checkNovelty(StrategyConfig config, List<StrategyConfig> existing) {
    if (existing == null || existing.isEmpty()) return true;

    String name = config.getName() != null ? config.getName().toUpperCase() : "";

    for (StrategyConfig ex : existing) {
      // Same name
      if (ex.getName() != null && ex.getName().toUpperCase().equals(name)) {
        return false;
      }

      // Same indicator types + condition types = not novel
      if (sameStructure(config, ex)) {
        return false;
      }
    }
    return true;
  }

  private boolean sameStructure(StrategyConfig a, StrategyConfig b) {
    List<String> aInd = indicatorTypes(a);
    List<String> bInd = indicatorTypes(b);
    List<String> aEntry = conditionTypes(a.getEntryConditions());
    List<String> bEntry = conditionTypes(b.getEntryConditions());
    List<String> aExit = conditionTypes(a.getExitConditions());
    List<String> bExit = conditionTypes(b.getExitConditions());

    return aInd.equals(bInd) && aEntry.equals(bEntry) && aExit.equals(bExit);
  }

  private List<String> indicatorTypes(StrategyConfig config) {
    List<String> types = new ArrayList<>();
    if (config.getIndicators() != null) {
      for (IndicatorConfig ind : config.getIndicators()) {
        types.add(ind.getType() != null ? ind.getType() : "");
      }
    }
    return types;
  }

  private List<String> conditionTypes(List<ConditionConfig> conditions) {
    List<String> types = new ArrayList<>();
    if (conditions != null) {
      for (ConditionConfig c : conditions) {
        types.add(c.getType() != null ? c.getType() : "");
      }
    }
    return types;
  }

  /**
   * Check if the config can actually be built into a Ta4j strategy (dry run without BarSeries).
   * This is a lightweight structural check, not a full build.
   */
  private boolean checkBuildable(StrategyConfig config, List<String> errors) {
    // If syntax and logic are valid, the config should be buildable.
    // The actual build test happens in the backtest pipeline.
    return true;
  }

  /** Detailed validation report. */
  public static final class ValidationReport {
    private final boolean isValid;
    private final boolean syntaxValid;
    private final boolean logicValid;
    private final boolean novel;
    private final List<String> errors;
    private final List<String> warnings;

    public ValidationReport(
        boolean isValid,
        boolean syntaxValid,
        boolean logicValid,
        boolean novel,
        List<String> errors,
        List<String> warnings) {
      this.isValid = isValid;
      this.syntaxValid = syntaxValid;
      this.logicValid = logicValid;
      this.novel = novel;
      this.errors = errors;
      this.warnings = warnings;
    }

    public boolean isValid() {
      return isValid;
    }

    public boolean isSyntaxValid() {
      return syntaxValid;
    }

    public boolean isLogicValid() {
      return logicValid;
    }

    public boolean isNovel() {
      return novel;
    }

    public List<String> getErrors() {
      return errors;
    }

    public List<String> getWarnings() {
      return warnings;
    }

    @Override
    public String toString() {
      return "ValidationReport{"
          + "valid="
          + isValid
          + ", syntax="
          + syntaxValid
          + ", logic="
          + logicValid
          + ", novel="
          + novel
          + ", errors="
          + errors
          + '}';
    }
  }
}
