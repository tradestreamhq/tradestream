package com.verlumen.tradestream.strategies.configurable;

/** Represents a single validation finding with a severity level and message. */
public final class ValidationResult {

  /** Severity levels for validation findings. */
  public enum Severity {
    ERROR,
    WARNING,
    INFO
  }

  private final Severity severity;
  private final String strategyName;
  private final String message;

  public ValidationResult(Severity severity, String strategyName, String message) {
    this.severity = severity;
    this.strategyName = strategyName;
    this.message = message;
  }

  public Severity getSeverity() {
    return severity;
  }

  public String getStrategyName() {
    return strategyName;
  }

  public String getMessage() {
    return message;
  }

  @Override
  public String toString() {
    return "[" + severity + "] " + strategyName + ": " + message;
  }

  public static ValidationResult error(String strategyName, String message) {
    return new ValidationResult(Severity.ERROR, strategyName, message);
  }

  public static ValidationResult warning(String strategyName, String message) {
    return new ValidationResult(Severity.WARNING, strategyName, message);
  }

  public static ValidationResult info(String strategyName, String message) {
    return new ValidationResult(Severity.INFO, strategyName, message);
  }
}
