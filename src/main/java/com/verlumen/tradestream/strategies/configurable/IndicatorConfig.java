package com.verlumen.tradestream.strategies.configurable;

import java.io.Serializable;
import java.util.Map;
import java.util.Objects;

/**
 * Configuration for a single indicator within a strategy. Defines the indicator type, its input
 * source, and parameters.
 */
public final class IndicatorConfig implements Serializable {
  private static final long serialVersionUID = 1L;

  private String id;
  private String type;
  private String input;
  private Map<String, String> params;

  public IndicatorConfig() {}

  public IndicatorConfig(String id, String type, String input, Map<String, String> params) {
    this.id = id;
    this.type = type;
    this.input = input;
    this.params = params;
  }

  public String getId() {
    return id;
  }

  public void setId(String id) {
    this.id = id;
  }

  public String getType() {
    return type;
  }

  public void setType(String type) {
    this.type = type;
  }

  public String getInput() {
    return input;
  }

  public void setInput(String input) {
    this.input = input;
  }

  public Map<String, String> getParams() {
    return params;
  }

  public void setParams(Map<String, String> params) {
    this.params = params;
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (o == null || getClass() != o.getClass()) return false;
    IndicatorConfig that = (IndicatorConfig) o;
    return Objects.equals(id, that.id)
        && Objects.equals(type, that.type)
        && Objects.equals(input, that.input)
        && Objects.equals(params, that.params);
  }

  @Override
  public int hashCode() {
    return Objects.hash(id, type, input, params);
  }

  @Override
  public String toString() {
    return "IndicatorConfig{"
        + "id='"
        + id
        + '\''
        + ", type='"
        + type
        + '\''
        + ", input='"
        + input
        + '\''
        + ", params="
        + params
        + '}';
  }

  public static Builder builder() {
    return new Builder();
  }

  public static final class Builder {
    private String id;
    private String type;
    private String input;
    private Map<String, String> params;

    private Builder() {}

    public Builder id(String id) {
      this.id = id;
      return this;
    }

    public Builder type(String type) {
      this.type = type;
      return this;
    }

    public Builder input(String input) {
      this.input = input;
      return this;
    }

    public Builder params(Map<String, String> params) {
      this.params = params;
      return this;
    }

    public IndicatorConfig build() {
      return new IndicatorConfig(id, type, input, params);
    }
  }
}
