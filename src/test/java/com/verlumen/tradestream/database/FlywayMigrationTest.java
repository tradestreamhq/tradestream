package com.verlumen.tradestream.database;

import static com.google.common.truth.Truth.assertThat;

import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.HashSet;
import java.util.Set;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.MigrationInfo;
import org.flywaydb.core.api.output.MigrateResult;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

/** Verifies that the Flyway SQL migrations apply cleanly against an in-memory H2 database. */
public final class FlywayMigrationTest {

  private org.h2.jdbcx.JdbcDataSource dataSource;

  @Before
  public void setUp() {
    dataSource = new org.h2.jdbcx.JdbcDataSource();
    dataSource.setURL("jdbc:h2:mem:flyway_test;DB_CLOSE_DELAY=-1;MODE=PostgreSQL");
    dataSource.setUser("sa");
    dataSource.setPassword("");
  }

  @After
  public void tearDown() throws SQLException {
    try (Connection conn = dataSource.getConnection();
        java.sql.Statement stmt = conn.createStatement()) {
      stmt.execute("SHUTDOWN");
    }
  }

  @Test
  public void migrationsApplyCleanly() {
    Flyway flyway =
        Flyway.configure()
            .dataSource(dataSource)
            .locations("classpath:database/migrations")
            .baselineOnMigrate(true)
            .load();

    MigrateResult result = flyway.migrate();

    assertThat(result.migrationsExecuted).isGreaterThan(0);
  }

  @Test
  public void strategySpecsTableCreated() throws SQLException {
    Flyway flyway =
        Flyway.configure()
            .dataSource(dataSource)
            .locations("classpath:database/migrations")
            .baselineOnMigrate(true)
            .load();
    flyway.migrate();

    Set<String> tables = getTableNames();
    assertThat(tables).contains("STRATEGY_SPECS");
  }

  @Test
  public void strategyImplementationsTableCreated() throws SQLException {
    Flyway flyway =
        Flyway.configure()
            .dataSource(dataSource)
            .locations("classpath:database/migrations")
            .baselineOnMigrate(true)
            .load();
    flyway.migrate();

    Set<String> tables = getTableNames();
    assertThat(tables).contains("STRATEGY_IMPLEMENTATIONS");
  }

  @Test
  public void strategyPerformanceTableCreated() throws SQLException {
    Flyway flyway =
        Flyway.configure()
            .dataSource(dataSource)
            .locations("classpath:database/migrations")
            .baselineOnMigrate(true)
            .load();
    flyway.migrate();

    Set<String> tables = getTableNames();
    assertThat(tables).contains("STRATEGY_PERFORMANCE");
  }

  @Test
  public void allMigrationsSucceed() {
    Flyway flyway =
        Flyway.configure()
            .dataSource(dataSource)
            .locations("classpath:database/migrations")
            .baselineOnMigrate(true)
            .load();
    flyway.migrate();

    MigrationInfo[] infos = flyway.info().all();
    for (MigrationInfo info : infos) {
      assertThat(info.getState().isApplied()).isTrue();
    }
  }

  private Set<String> getTableNames() throws SQLException {
    Set<String> tables = new HashSet<>();
    try (Connection conn = dataSource.getConnection()) {
      DatabaseMetaData meta = conn.getMetaData();
      try (ResultSet rs = meta.getTables(null, null, "%", new String[] {"TABLE"})) {
        while (rs.next()) {
          tables.add(rs.getString("TABLE_NAME"));
        }
      }
    }
    return tables;
  }
}
