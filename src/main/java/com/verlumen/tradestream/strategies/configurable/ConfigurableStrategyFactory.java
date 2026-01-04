package com.verlumen.tradestream.strategies.configurable;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.ConfigurableStrategyParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseStrategy;
import org.ta4j.core.Indicator;
import org.ta4j.core.Rule;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.Num;

/**
 * A StrategyFactory that builds Ta4j strategies from config definitions. Implements the existing
 * StrategyFactory interface to maintain compatibility with the GA pipeline and backtesting
 * infrastructure.
 */
public final class ConfigurableStrategyFactory
    implements StrategyFactory<ConfigurableStrategyParameters> {

  private static final Pattern PARAM_REFERENCE_PATTERN = Pattern.compile("\\$\\{([^}]+)}");

  private final StrategyConfig config;
  private final IndicatorRegistry indicatorRegistry;
  private final RuleRegistry ruleRegistry;

  public ConfigurableStrategyFactory(StrategyConfig config) {
    this(config, IndicatorRegistry.defaultRegistry(), RuleRegistry.defaultRegistry());
  }

  public ConfigurableStrategyFactory(
      StrategyConfig config, IndicatorRegistry indicatorRegistry, RuleRegistry ruleRegistry) {
    this.config = config;
    this.indicatorRegistry = indicatorRegistry;
    this.ruleRegistry = ruleRegistry;
  }

  @Override
  public Strategy createStrategy(BarSeries barSeries, ConfigurableStrategyParameters parameters)
      throws InvalidProtocolBufferException {
    // 1. Build indicators from config
    Map<String, Indicator<Num>> indicators = buildIndicators(barSeries, parameters);

    // 2. Build entry rule from config
    Rule entryRule = buildRule(config.getEntryConditions(), barSeries, indicators);

    // 3. Build exit rule from config
    Rule exitRule = buildRule(config.getExitConditions(), barSeries, indicators);

    // 4. Calculate unstable period
    int unstablePeriod = calculateUnstablePeriod();

    return new BaseStrategy(config.getName(), entryRule, exitRule, unstablePeriod);
  }

  @Override
  public ConfigurableStrategyParameters getDefaultParameters() {
    ConfigurableStrategyParameters.Builder builder = ConfigurableStrategyParameters.newBuilder();

    if (config.getParameters() != null) {
      for (ParameterDefinition param : config.getParameters()) {
        if (param.getDefaultValue() != null) {
          if (param.getType() == ParameterType.INTEGER) {
            builder.putIntValues(param.getName(), param.getDefaultValue().intValue());
          } else if (param.getType() == ParameterType.DOUBLE) {
            builder.putDoubleValues(param.getName(), param.getDefaultValue().doubleValue());
          }
        }
      }
    }

    return builder.build();
  }

  private Map<String, Indicator<Num>> buildIndicators(
      BarSeries barSeries, ConfigurableStrategyParameters params) {

    Map<String, Indicator<Num>> indicators = new HashMap<>();

    // Always add close price as a base indicator
    ClosePriceIndicator closePrice = new ClosePriceIndicator(barSeries);
    indicators.put("close", closePrice);

    if (config.getIndicators() == null) {
      return indicators;
    }

    for (IndicatorConfig indicatorConfig : config.getIndicators()) {
      Indicator<Num> input = resolveInput(indicatorConfig.getInput(), barSeries, indicators);
      ResolvedParams resolvedParams = resolveParams(indicatorConfig.getParams(), params);

      Indicator<Num> indicator =
          indicatorRegistry.create(indicatorConfig.getType(), barSeries, input, resolvedParams);

      indicators.put(indicatorConfig.getId(), indicator);
    }

    return indicators;
  }

  private Indicator<Num> resolveInput(
      String input, BarSeries barSeries, Map<String, Indicator<Num>> indicators) {

    if (input == null || input.isEmpty() || input.equalsIgnoreCase("close")) {
      return indicators.computeIfAbsent("close", k -> new ClosePriceIndicator(barSeries));
    }

    if (input.equalsIgnoreCase("high")) {
      return indicators.computeIfAbsent(
          "high",
          k -> indicatorRegistry.create("HIGH", barSeries, null, new ResolvedParams(Map.of())));
    }

    if (input.equalsIgnoreCase("low")) {
      return indicators.computeIfAbsent(
          "low",
          k -> indicatorRegistry.create("LOW", barSeries, null, new ResolvedParams(Map.of())));
    }

    if (input.equalsIgnoreCase("open")) {
      return indicators.computeIfAbsent(
          "open",
          k -> indicatorRegistry.create("OPEN", barSeries, null, new ResolvedParams(Map.of())));
    }

    if (input.equalsIgnoreCase("volume")) {
      return indicators.computeIfAbsent(
          "volume",
          k -> indicatorRegistry.create("VOLUME", barSeries, null, new ResolvedParams(Map.of())));
    }

    // Otherwise, look up by indicator ID
    Indicator<Num> indicator = indicators.get(input);
    if (indicator == null) {
      throw new IllegalArgumentException(
          "Unknown input indicator: " + input + ". Make sure indicators are defined in order.");
    }
    return indicator;
  }

  private ResolvedParams resolveParams(
      Map<String, String> configParams, ConfigurableStrategyParameters strategyParams) {

    if (configParams == null || configParams.isEmpty()) {
      return new ResolvedParams(Map.of());
    }

    Map<String, Object> resolved = new HashMap<>();

    for (Map.Entry<String, String> entry : configParams.entrySet()) {
      String key = entry.getKey();
      String value = entry.getValue();

      if (value == null) {
        continue;
      }

      // Check if value is a parameter reference like ${paramName}
      Matcher matcher = PARAM_REFERENCE_PATTERN.matcher(value);
      if (matcher.matches()) {
        String paramName = matcher.group(1);
        Object resolvedValue = resolveParameterReference(paramName, strategyParams);
        resolved.put(key, resolvedValue);
      } else {
        // Try to parse as number, otherwise keep as string
        resolved.put(key, parseValue(value));
      }
    }

    return new ResolvedParams(resolved);
  }

  private Object resolveParameterReference(
      String paramName, ConfigurableStrategyParameters params) {

    if (params.getIntValuesMap().containsKey(paramName)) {
      return params.getIntValuesMap().get(paramName);
    }

    if (params.getDoubleValuesMap().containsKey(paramName)) {
      return params.getDoubleValuesMap().get(paramName);
    }

    // Fall back to config default
    if (config.getParameters() != null) {
      for (ParameterDefinition paramDef : config.getParameters()) {
        if (paramDef.getName().equals(paramName) && paramDef.getDefaultValue() != null) {
          return paramDef.getDefaultValue();
        }
      }
    }

    throw new IllegalArgumentException("Unknown parameter: " + paramName);
  }

  private Object parseValue(String value) {
    // Try integer
    try {
      return Integer.parseInt(value);
    } catch (NumberFormatException e) {
      // Not an integer
    }

    // Try double
    try {
      return Double.parseDouble(value);
    } catch (NumberFormatException e) {
      // Not a double
    }

    // Return as string
    return value;
  }

  private Rule buildRule(
      List<ConditionConfig> conditions,
      BarSeries barSeries,
      Map<String, Indicator<Num>> indicators) {

    if (conditions == null || conditions.isEmpty()) {
      throw new IllegalArgumentException("Strategy must have at least one condition");
    }

    Rule combinedRule = null;

    for (ConditionConfig condition : conditions) {
      ResolvedParams params = new ResolvedParams(condition.getParams());

      // Add the indicator reference to params if specified
      Map<String, Object> augmentedParams = new HashMap<>();
      if (condition.getParams() != null) {
        augmentedParams.putAll(condition.getParams());
      }
      if (condition.getIndicator() != null) {
        augmentedParams.put("indicator", condition.getIndicator());
      }

      Rule rule =
          ruleRegistry.create(
              condition.getType(), barSeries, indicators, new ResolvedParams(augmentedParams));

      combinedRule = (combinedRule == null) ? rule : combinedRule.and(rule);
    }

    return combinedRule;
  }

  private int calculateUnstablePeriod() {
    int maxPeriod = 0;

    if (config.getParameters() != null) {
      for (ParameterDefinition param : config.getParameters()) {
        if (param.getType() == ParameterType.INTEGER && param.getDefaultValue() != null) {
          maxPeriod = Math.max(maxPeriod, param.getDefaultValue().intValue());
        }
      }
    }

    // Minimum unstable period of 1
    return Math.max(1, maxPeriod);
  }

  public StrategyConfig getConfig() {
    return config;
  }
}
