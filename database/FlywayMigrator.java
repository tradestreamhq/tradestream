package com.verlumen.tradestream.database;

import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationInfo;
import org.flywaydb.core.api.output.MigrateResult;

/**
 * CLI tool for running Flyway database migrations against a PostgreSQL database. Reads connection
 * parameters from environment variables or command-line arguments.
 *
 * <p>Usage: bazel run //database:migrate -- --url=jdbc:postgresql://host:5432/db --user=user
 * --password=pass
 *
 * <p>Or set environment variables: FLYWAY_URL, FLYWAY_USER, FLYWAY_PASSWORD
 */
public final class FlywayMigrator {

  private static final String DEFAULT_MIGRATION_LOCATION = "classpath:database/migrations";

  public static void main(String[] args) {
    String url = getConfig(args, "url", "FLYWAY_URL", null);
    String user = getConfig(args, "user", "FLYWAY_USER", null);
    String password = getConfig(args, "password", "FLYWAY_PASSWORD", "");
    String action = getConfig(args, "action", "FLYWAY_ACTION", "migrate");

    if (url == null || user == null) {
      System.err.println("Usage: migrate --url=<jdbc-url> --user=<user> [--password=<pass>]");
      System.err.println("  Or set FLYWAY_URL, FLYWAY_USER, FLYWAY_PASSWORD env vars.");
      System.err.println("  Optional: --action=<migrate|info|validate|repair>");
      System.exit(1);
    }

    Flyway flyway =
        Flyway.configure()
            .dataSource(url, user, password)
            .locations(DEFAULT_MIGRATION_LOCATION)
            .baselineOnMigrate(true)
            .load();

    switch (action.toLowerCase()) {
      case "info":
        printInfo(flyway);
        break;
      case "validate":
        flyway.validate();
        System.out.println("Validation successful.");
        break;
      case "repair":
        flyway.repair();
        System.out.println("Repair completed.");
        break;
      case "migrate":
      default:
        MigrateResult result = flyway.migrate();
        System.out.println(
            "Successfully applied " + result.migrationsExecuted + " migration(s).");
        printInfo(flyway);
        break;
    }
  }

  private static void printInfo(Flyway flyway) {
    MigrationInfo[] infos = flyway.info().all();
    System.out.println("\nMigration Status:");
    System.out.printf("%-30s %-10s %-20s%n", "Version", "State", "Description");
    System.out.println("-".repeat(60));
    for (MigrationInfo info : infos) {
      System.out.printf(
          "%-30s %-10s %-20s%n",
          info.getVersion(), info.getState(), info.getDescription());
    }
  }

  private static String getConfig(
      String[] args, String argName, String envName, String defaultValue) {
    // Check command-line args first
    String prefix = "--" + argName + "=";
    for (String arg : args) {
      if (arg.startsWith(prefix)) {
        return arg.substring(prefix.length());
      }
    }

    // Fall back to environment variable
    String envValue = System.getenv(envName);
    if (envValue != null && !envValue.isEmpty()) {
      return envValue;
    }

    return defaultValue;
  }
}
