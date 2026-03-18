package com.verlumen.tradestream.database;

import static com.google.common.truth.Truth.assertThat;

import java.io.File;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationInfo;
import org.junit.Before;
import org.junit.Test;

/**
 * Verifies that Flyway can discover and parse the SQL migration files. Uses filesystem location
 * since Bazel data runfiles are not on the classpath.
 */
public final class FlywayMigrationTest {

  private org.h2.jdbcx.JdbcDataSource dataSource;
  private String migrationsPath;

  @Before
  public void setUp() {
    dataSource = new org.h2.jdbcx.JdbcDataSource();
    dataSource.setURL("jdbc:h2:mem:flyway_discovery;DB_CLOSE_DELAY=-1;MODE=PostgreSQL");
    dataSource.setUser("sa");
    dataSource.setPassword("");

    // Resolve the migrations directory from Bazel runfiles
    String runfilesDir = System.getenv("TEST_SRCDIR");
    if (runfilesDir != null) {
      migrationsPath = runfilesDir + "/_main/database/migrations";
    } else {
      migrationsPath = "database/migrations";
    }
  }

  @Test
  public void flywayDiscoversMigrations() {
    Flyway flyway =
        Flyway.configure()
            .dataSource(dataSource)
            .locations("filesystem:" + migrationsPath)
            .load();

    MigrationInfo[] pending = flyway.info().pending();

    assertThat(pending.length).isGreaterThan(0);
  }

  @Test
  public void strategySpecsMigrationDiscovered() {
    Flyway flyway =
        Flyway.configure()
            .dataSource(dataSource)
            .locations("filesystem:" + migrationsPath)
            .load();

    MigrationInfo[] all = flyway.info().all();

    boolean found = false;
    for (MigrationInfo info : all) {
      if (info.getDescription() != null
          && info.getDescription().toLowerCase().contains("strategy specs")) {
        found = true;
        break;
      }
    }
    assertThat(found).isTrue();
  }

  @Test
  public void baselineMigrationDiscovered() {
    Flyway flyway =
        Flyway.configure()
            .dataSource(dataSource)
            .locations("filesystem:" + migrationsPath)
            .load();

    MigrationInfo[] all = flyway.info().all();

    boolean found = false;
    for (MigrationInfo info : all) {
      if (info.getVersion() != null && info.getVersion().toString().equals("1")) {
        found = true;
        break;
      }
    }
    assertThat(found).isTrue();
  }

  @Test
  public void performanceMigrationDiscovered() {
    Flyway flyway =
        Flyway.configure()
            .dataSource(dataSource)
            .locations("filesystem:" + migrationsPath)
            .load();

    MigrationInfo[] all = flyway.info().all();

    boolean found = false;
    for (MigrationInfo info : all) {
      if (info.getDescription() != null
          && info.getDescription().toLowerCase().contains("strategy performance")) {
        found = true;
        break;
      }
    }
    assertThat(found).isTrue();
  }
}
