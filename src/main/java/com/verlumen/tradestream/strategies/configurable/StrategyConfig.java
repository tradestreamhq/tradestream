package com.verlumen.tradestream.strategies.configurable;

import java.io.Serializable;
import java.util.List;
import java.util.Objects;

/**
 * POJO representing a strategy configuration loaded from YAML/JSON/Database. This is the top-level
 * configuration object that defines a complete trading strategy.
 */
public final class StrategyConfig implements Serializable {
  private static final long serialVersionUID = 1L;

  private String name;
  private String description;
  private String complexity;
  private String source;
  private String sourceStrategy;

  private List<IndicatorConfig> indicators;
  private List<ConditionConfig> entryConditions;
  private List<ConditionConfig> exitConditions;
  private List<ParameterDefinition> parameters;

  public StrategyConfig() {}

  public StrategyConfig(
      String name,
      String description,
      String complexity,
      String source,
      String sourceStrategy,
      List<IndicatorConfig> indicators,
      List<ConditionConfig> entryConditions,
      List<ConditionConfig> exitConditions,
      List<ParameterDefinition> parameters) {
    this.name = name;
    this.description = description;
    this.complexity = complexity;
    this.source = source;
    this.sourceStrategy = sourceStrategy;
    this.indicators = indicators;
    this.entryConditions = entryConditions;
    this.exitConditions = exitConditions;
    this.parameters = parameters;
  }

  public String getName() {
    return name;
  }

  public void setName(String name) {
    this.name = name;
  }

  public String getDescription() {
    return description;
  }

  public void setDescription(String description) {
    this.description = description;
  }

  public String getComplexity() {
    return complexity;
  }

  public void setComplexity(String complexity) {
    this.complexity = complexity;
  }

  public String getSource() {
    return source;
  }

  public void setSource(String source) {
    this.source = source;
  }

  public String getSourceStrategy() {
    return sourceStrategy;
  }

  public void setSourceStrategy(String sourceStrategy) {
    this.sourceStrategy = sourceStrategy;
  }

  public List<IndicatorConfig> getIndicators() {
    return indicators;
  }

  public void setIndicators(List<IndicatorConfig> indicators) {
    this.indicators = indicators;
  }

  public List<ConditionConfig> getEntryConditions() {
    return entryConditions;
  }

  public void setEntryConditions(List<ConditionConfig> entryConditions) {
    this.entryConditions = entryConditions;
  }

  public List<ConditionConfig> getExitConditions() {
    return exitConditions;
  }

  public void setExitConditions(List<ConditionConfig> exitConditions) {
    this.exitConditions = exitConditions;
  }

  public List<ParameterDefinition> getParameters() {
    return parameters;
  }

  public void setParameters(List<ParameterDefinition> parameters) {
    this.parameters = parameters;
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (o == null || getClass() != o.getClass()) return false;
    StrategyConfig that = (StrategyConfig) o;
    return Objects.equals(name, that.name)
        && Objects.equals(description, that.description)
        && Objects.equals(complexity, that.complexity)
        && Objects.equals(source, that.source)
        && Objects.equals(sourceStrategy, that.sourceStrategy)
        && Objects.equals(indicators, that.indicators)
        && Objects.equals(entryConditions, that.entryConditions)
        && Objects.equals(exitConditions, that.exitConditions)
        && Objects.equals(parameters, that.parameters);
  }

  @Override
  public int hashCode() {
    return Objects.hash(
        name,
        description,
        complexity,
        source,
        sourceStrategy,
        indicators,
        entryConditions,
        exitConditions,
        parameters);
  }

  @Override
  public String toString() {
    return "StrategyConfig{"
        + "name='"
        + name
        + '\''
        + ", description='"
        + description
        + '\''
        + ", complexity='"
        + complexity
        + '\''
        + ", source='"
        + source
        + '\''
        + ", sourceStrategy='"
        + sourceStrategy
        + '\''
        + ", indicators="
        + indicators
        + ", entryConditions="
        + entryConditions
        + ", exitConditions="
        + exitConditions
        + ", parameters="
        + parameters
        + '}';
  }

  public static Builder builder() {
    return new Builder();
  }

  public static final class Builder {
    private String name;
    private String description;
    private String complexity;
    private String source;
    private String sourceStrategy;
    private List<IndicatorConfig> indicators;
    private List<ConditionConfig> entryConditions;
    private List<ConditionConfig> exitConditions;
    private List<ParameterDefinition> parameters;

    private Builder() {}

    public Builder name(String name) {
      this.name = name;
      return this;
    }

    public Builder description(String description) {
      this.description = description;
      return this;
    }

    public Builder complexity(String complexity) {
      this.complexity = complexity;
      return this;
    }

    public Builder source(String source) {
      this.source = source;
      return this;
    }

    public Builder sourceStrategy(String sourceStrategy) {
      this.sourceStrategy = sourceStrategy;
      return this;
    }

    public Builder indicators(List<IndicatorConfig> indicators) {
      this.indicators = indicators;
      return this;
    }

    public Builder entryConditions(List<ConditionConfig> entryConditions) {
      this.entryConditions = entryConditions;
      return this;
    }

    public Builder exitConditions(List<ConditionConfig> exitConditions) {
      this.exitConditions = exitConditions;
      return this;
    }

    public Builder parameters(List<ParameterDefinition> parameters) {
      this.parameters = parameters;
      return this;
    }

    public StrategyConfig build() {
      return new StrategyConfig(
          name,
          description,
          complexity,
          source,
          sourceStrategy,
          indicators,
          entryConditions,
          exitConditions,
          parameters);
    }
  }
}
