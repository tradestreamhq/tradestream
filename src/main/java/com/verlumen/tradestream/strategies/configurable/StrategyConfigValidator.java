package com.verlumen.tradestream.strategies.configurable;

import java.util.List;

/**
 * CLI entry point for pre-deployment strategy configuration validation. Validates all registered
 * strategy configs and reports results with severity levels. Exits with code 1 if any errors are
 * found.
 */
public final class StrategyConfigValidator {

  private StrategyConfigValidator() {}

  public static void main(String[] args) {
    StrategyConfigValidationService service = StrategyConfigValidationService.createDefault();

    List<ValidationResult> results;
    if (args.length > 0) {
      // Validate specific files passed as arguments
      results = new java.util.ArrayList<>();
      for (String path : args) {
        try {
          StrategyConfig config = StrategyConfigLoader.load(path);
          results.addAll(service.validate(config));
        } catch (Exception e) {
          results.add(ValidationResult.error(path, "Failed to load: " + e.getMessage()));
        }
      }
    } else {
      // Validate all registered strategies
      results = service.validateAll();
    }

    int errors = 0;
    int warnings = 0;
    int infos = 0;

    for (ValidationResult result : results) {
      System.out.println(result);
      switch (result.getSeverity()) {
        case ERROR:
          errors++;
          break;
        case WARNING:
          warnings++;
          break;
        case INFO:
          infos++;
          break;
      }
    }

    System.out.println();
    System.out.println(
        "Validation complete: "
            + errors
            + " error(s), "
            + warnings
            + " warning(s), "
            + infos
            + " info(s)");

    if (errors > 0) {
      System.out.println("VALIDATION FAILED");
      System.exit(1);
    } else {
      System.out.println("VALIDATION PASSED");
    }
  }
}
