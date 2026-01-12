package com.verlumen.tradestream.strategies.configurable;

import java.util.Map;

/**
 * Utility class for accessing resolved parameter values. Provides type-safe access to parameters
 * that may have been resolved from config templates (e.g., ${param_name} references).
 */
public final class ResolvedParams {
  private final Map<String, Object> params;

  public ResolvedParams(Map<String, Object> params) {
    this.params = params;
  }

  public int getInt(String key) {
    Object value = params.get(key);
    if (value == null) {
      throw new IllegalArgumentException("Missing required parameter: " + key);
    }
    if (value instanceof Number) {
      return ((Number) value).intValue();
    }
    return Integer.parseInt(value.toString());
  }

  public int getInt(String key, int defaultValue) {
    Object value = params.get(key);
    if (value == null) {
      return defaultValue;
    }
    if (value instanceof Number) {
      return ((Number) value).intValue();
    }
    return Integer.parseInt(value.toString());
  }

  public double getDouble(String key) {
    Object value = params.get(key);
    if (value == null) {
      throw new IllegalArgumentException("Missing required parameter: " + key);
    }
    if (value instanceof Number) {
      return ((Number) value).doubleValue();
    }
    return Double.parseDouble(value.toString());
  }

  public double getDouble(String key, double defaultValue) {
    Object value = params.get(key);
    if (value == null) {
      return defaultValue;
    }
    if (value instanceof Number) {
      return ((Number) value).doubleValue();
    }
    return Double.parseDouble(value.toString());
  }

  public String getString(String key) {
    Object value = params.get(key);
    if (value == null) {
      throw new IllegalArgumentException("Missing required parameter: " + key);
    }
    return value.toString();
  }

  public String getString(String key, String defaultValue) {
    Object value = params.get(key);
    if (value == null) {
      return defaultValue;
    }
    return value.toString();
  }

  public boolean containsKey(String key) {
    return params.containsKey(key);
  }

  public Object get(String key) {
    return params.get(key);
  }

  public Map<String, Object> asMap() {
    return Map.copyOf(params);
  }
}
