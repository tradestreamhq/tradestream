package com.verlumen.tradestream.strategies.configurable;

import java.io.Serializable;
import java.util.Objects;

/**
 * Definition for a strategy parameter that can be optimized by the GA. Specifies the parameter
 * name, type, valid range, and default value.
 */
public final class ParameterDefinition implements Serializable {
  private static final long serialVersionUID = 1L;

  private String name;
  private ParameterType type;
  private Number min;
  private Number max;
  private Number defaultValue;

  public ParameterDefinition() {}

  public ParameterDefinition(
      String name, ParameterType type, Number min, Number max, Number defaultValue) {
    this.name = name;
    this.type = type;
    this.min = min;
    this.max = max;
    this.defaultValue = defaultValue;
  }

  public String getName() {
    return name;
  }

  public void setName(String name) {
    this.name = name;
  }

  public ParameterType getType() {
    return type;
  }

  public void setType(ParameterType type) {
    this.type = type;
  }

  public Number getMin() {
    return min;
  }

  public void setMin(Number min) {
    this.min = min;
  }

  public Number getMax() {
    return max;
  }

  public void setMax(Number max) {
    this.max = max;
  }

  public Number getDefaultValue() {
    return defaultValue;
  }

  public void setDefaultValue(Number defaultValue) {
    this.defaultValue = defaultValue;
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (o == null || getClass() != o.getClass()) return false;
    ParameterDefinition that = (ParameterDefinition) o;
    return Objects.equals(name, that.name)
        && type == that.type
        && Objects.equals(min, that.min)
        && Objects.equals(max, that.max)
        && Objects.equals(defaultValue, that.defaultValue);
  }

  @Override
  public int hashCode() {
    return Objects.hash(name, type, min, max, defaultValue);
  }

  @Override
  public String toString() {
    return "ParameterDefinition{"
        + "name='"
        + name
        + '\''
        + ", type="
        + type
        + ", min="
        + min
        + ", max="
        + max
        + ", defaultValue="
        + defaultValue
        + '}';
  }

  public static Builder builder() {
    return new Builder();
  }

  public static final class Builder {
    private String name;
    private ParameterType type;
    private Number min;
    private Number max;
    private Number defaultValue;

    private Builder() {}

    public Builder name(String name) {
      this.name = name;
      return this;
    }

    public Builder type(ParameterType type) {
      this.type = type;
      return this;
    }

    public Builder min(Number min) {
      this.min = min;
      return this;
    }

    public Builder max(Number max) {
      this.max = max;
      return this;
    }

    public Builder defaultValue(Number defaultValue) {
      this.defaultValue = defaultValue;
      return this;
    }

    public ParameterDefinition build() {
      return new ParameterDefinition(name, type, min, max, defaultValue);
    }
  }
}
