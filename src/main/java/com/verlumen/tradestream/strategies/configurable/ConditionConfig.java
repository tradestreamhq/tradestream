package com.verlumen.tradestream.strategies.configurable;

import java.io.Serializable;
import java.util.Map;
import java.util.Objects;

/**
 * Configuration for a single condition (entry or exit) within a strategy. Defines the condition
 * type and its parameters.
 */
public final class ConditionConfig implements Serializable {
  private static final long serialVersionUID = 1L;

  private String type;
  private String indicator;
  private Map<String, Object> params;

  public ConditionConfig() {}

  public ConditionConfig(String type, String indicator, Map<String, Object> params) {
    this.type = type;
    this.indicator = indicator;
    this.params = params;
  }

  public String getType() {
    return type;
  }

  public void setType(String type) {
    this.type = type;
  }

  public String getIndicator() {
    return indicator;
  }

  public void setIndicator(String indicator) {
    this.indicator = indicator;
  }

  public Map<String, Object> getParams() {
    return params;
  }

  public void setParams(Map<String, Object> params) {
    this.params = params;
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (o == null || getClass() != o.getClass()) return false;
    ConditionConfig that = (ConditionConfig) o;
    return Objects.equals(type, that.type)
        && Objects.equals(indicator, that.indicator)
        && Objects.equals(params, that.params);
  }

  @Override
  public int hashCode() {
    return Objects.hash(type, indicator, params);
  }

  @Override
  public String toString() {
    return "ConditionConfig{"
        + "type='"
        + type
        + '\''
        + ", indicator='"
        + indicator
        + '\''
        + ", params="
        + params
        + '}';
  }

  public static Builder builder() {
    return new Builder();
  }

  public static final class Builder {
    private String type;
    private String indicator;
    private Map<String, Object> params;

    private Builder() {}

    public Builder type(String type) {
      this.type = type;
      return this;
    }

    public Builder indicator(String indicator) {
      this.indicator = indicator;
      return this;
    }

    public Builder params(Map<String, Object> params) {
      this.params = params;
      return this;
    }

    public ConditionConfig build() {
      return new ConditionConfig(type, indicator, params);
    }
  }
}
