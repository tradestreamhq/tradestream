package com.verlumen.tradestream.strategies.configurable.db;

import static com.google.common.truth.Truth.assertThat;

import com.google.gson.Gson;
import com.verlumen.tradestream.strategies.configurable.ConditionConfig;
import com.verlumen.tradestream.strategies.configurable.IndicatorConfig;
import com.verlumen.tradestream.strategies.configurable.ParameterDefinition;
import com.verlumen.tradestream.strategies.configurable.ParameterType;
import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.Duration;
import java.time.ZonedDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import javax.sql.DataSource;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;
import org.ta4j.core.num.DecimalNum;

/**
 * Tests for ConfigDrivenStrategyBuilder using an in-memory H2 database that emulates the
 * strategy_specs schema.
 */
public final class ConfigDrivenStrategyBuilderTest {

  private static final Gson GSON = new Gson();

  private InMemoryDataSource dataSource;
  private ConfigDrivenStrategyBuilder builder;

  @Before
  public void setUp() throws Exception {
    dataSource = new InMemoryDataSource();
    createSchema(dataSource);
    builder = new ConfigDrivenStrategyBuilder(dataSource);
  }

  @After
  public void tearDown() throws Exception {
    dataSource.close();
  }

  @Test
  public void loadAllSpecs_emptyTable_returnsEmptyList() throws Exception {
    List<StrategyConfig> specs = builder.loadAllSpecs();
    assertThat(specs).isEmpty();
  }

  @Test
  public void loadAllSpecs_withActiveSpec_returnsSpec() throws Exception {
    insertTestSpec("TEST_STRATEGY", true);

    List<StrategyConfig> specs = builder.loadAllSpecs();

    assertThat(specs).hasSize(1);
    assertThat(specs.get(0).getName()).isEqualTo("TEST_STRATEGY");
  }

  @Test
  public void loadAllSpecs_inactiveSpec_excluded() throws Exception {
    insertTestSpec("INACTIVE_STRATEGY", false);

    List<StrategyConfig> specs = builder.loadAllSpecs();
    assertThat(specs).isEmpty();
  }

  @Test
  public void loadSpec_existingName_returnsConfig() throws Exception {
    insertTestSpec("SMA_EMA_CROSSOVER", true);

    Optional<StrategyConfig> config = builder.loadSpec("SMA_EMA_CROSSOVER");

    assertThat(config.isPresent()).isTrue();
    assertThat(config.get().getName()).isEqualTo("SMA_EMA_CROSSOVER");
    assertThat(config.get().getIndicators()).hasSize(2);
    assertThat(config.get().getEntryConditions()).hasSize(1);
    assertThat(config.get().getExitConditions()).hasSize(1);
    assertThat(config.get().getParameters()).hasSize(2);
  }

  @Test
  public void loadSpec_nonExistentName_returnsEmpty() throws Exception {
    Optional<StrategyConfig> config = builder.loadSpec("DOES_NOT_EXIST");
    assertThat(config.isPresent()).isFalse();
  }

  @Test
  public void buildStrategy_validSpec_returnsStrategy() throws Exception {
    insertTestSpec("SMA_EMA_CROSSOVER", true);
    BarSeries barSeries = createTestBarSeries();

    Optional<Strategy> strategy = builder.buildStrategy("SMA_EMA_CROSSOVER", barSeries);

    assertThat(strategy.isPresent()).isTrue();
    assertThat(strategy.get().getEntryRule()).isNotNull();
    assertThat(strategy.get().getExitRule()).isNotNull();
  }

  @Test
  public void buildStrategy_nonExistent_returnsEmpty() throws Exception {
    BarSeries barSeries = createTestBarSeries();

    Optional<Strategy> strategy = builder.buildStrategy("MISSING", barSeries);
    assertThat(strategy.isPresent()).isFalse();
  }

  @Test
  public void buildAllStrategies_multipleSpecs_buildsAll() throws Exception {
    insertTestSpec("STRATEGY_A", true);
    insertTestSpec("STRATEGY_B", true);
    BarSeries barSeries = createTestBarSeries();

    List<ConfigDrivenStrategyBuilder.NamedStrategy> strategies =
        builder.buildAllStrategies(barSeries);

    assertThat(strategies).hasSize(2);
  }

  @Test
  public void loadSpec_parsesParameterRanges() throws Exception {
    insertTestSpec("SMA_EMA_CROSSOVER", true);

    StrategyConfig config = builder.loadSpec("SMA_EMA_CROSSOVER").get();
    ParameterDefinition smaPeriod = config.getParameters().get(0);

    assertThat(smaPeriod.getName()).isEqualTo("sma_period");
    assertThat(smaPeriod.getType()).isEqualTo(ParameterType.INTEGER);
    assertThat(smaPeriod.getMin().intValue()).isEqualTo(5);
    assertThat(smaPeriod.getMax().intValue()).isEqualTo(50);
    assertThat(smaPeriod.getDefaultValue().intValue()).isEqualTo(20);
  }

  // --- Test helpers ---

  private void createSchema(InMemoryDataSource ds) throws SQLException {
    try (Connection conn = ds.getConnection();
        Statement stmt = conn.createStatement()) {
      stmt.execute(
          "CREATE TABLE strategy_specs ("
              + "  id VARCHAR(36) DEFAULT RANDOM_UUID() PRIMARY KEY,"
              + "  name VARCHAR(255) UNIQUE NOT NULL,"
              + "  description TEXT,"
              + "  complexity VARCHAR(50),"
              + "  indicators TEXT NOT NULL,"
              + "  entry_conditions TEXT NOT NULL,"
              + "  exit_conditions TEXT NOT NULL,"
              + "  parameters TEXT NOT NULL,"
              + "  source VARCHAR(50) NOT NULL DEFAULT 'MIGRATED',"
              + "  is_active BOOLEAN NOT NULL DEFAULT TRUE,"
              + "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
              + "  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
              + ")");
    }
  }

  private void insertTestSpec(String name, boolean isActive) throws SQLException {
    List<IndicatorConfig> indicators =
        List.of(
            new IndicatorConfig("sma", "SMA", "close", Map.of("period", "${sma_period}")),
            new IndicatorConfig("ema", "EMA", "close", Map.of("period", "${ema_period}")));

    List<ConditionConfig> entryConditions =
        List.of(
            new ConditionConfig(
                "CROSSED_UP", "sma", Map.of("indicator", "sma", "crosses", "ema")));

    List<ConditionConfig> exitConditions =
        List.of(
            new ConditionConfig(
                "CROSSED_DOWN", "sma", Map.of("indicator", "sma", "crosses", "ema")));

    List<ParameterDefinition> parameters =
        List.of(
            new ParameterDefinition("sma_period", ParameterType.INTEGER, 5, 50, 20),
            new ParameterDefinition("ema_period", ParameterType.INTEGER, 5, 50, 10));

    try (Connection conn = dataSource.getConnection();
        PreparedStatement stmt =
            conn.prepareStatement(
                "INSERT INTO strategy_specs (name, description, complexity, indicators, "
                    + "entry_conditions, exit_conditions, parameters, is_active) "
                    + "VALUES (?, ?, ?, ?, ?, ?, ?, ?)")) {
      stmt.setString(1, name);
      stmt.setString(2, "Test strategy: " + name);
      stmt.setString(3, "SIMPLE");
      stmt.setString(4, GSON.toJson(indicators));
      stmt.setString(5, GSON.toJson(entryConditions));
      stmt.setString(6, GSON.toJson(exitConditions));
      stmt.setString(7, GSON.toJson(parameters));
      stmt.setBoolean(8, isActive);
      stmt.executeUpdate();
    }
  }

  private BarSeries createTestBarSeries() {
    BarSeries series = new BaseBarSeriesBuilder().withName("test").build();
    ZonedDateTime now = ZonedDateTime.now();
    // Add enough bars for indicator warm-up (50+ periods)
    for (int i = 0; i < 100; i++) {
      double price = 100.0 + Math.sin(i * 0.1) * 10;
      series.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i).toInstant().minus(Duration.ofMinutes(1)),
              now.plusMinutes(i).toInstant(),
              DecimalNum.valueOf(price),
              DecimalNum.valueOf(price + 1),
              DecimalNum.valueOf(price - 1),
              DecimalNum.valueOf(price + 0.5),
              DecimalNum.valueOf(1000 + i * 10),
              DecimalNum.valueOf(0),
              0));
    }
    return series;
  }

  /**
   * Simple in-memory DataSource backed by H2 for testing. Avoids requiring a real PostgreSQL
   * instance.
   */
  private static final class InMemoryDataSource implements DataSource, AutoCloseable {
    private final org.h2.jdbcx.JdbcDataSource delegate;

    InMemoryDataSource() {
      delegate = new org.h2.jdbcx.JdbcDataSource();
      delegate.setURL("jdbc:h2:mem:testdb;DB_CLOSE_DELAY=-1");
      delegate.setUser("sa");
      delegate.setPassword("");
    }

    @Override
    public Connection getConnection() throws SQLException {
      return delegate.getConnection();
    }

    @Override
    public Connection getConnection(String username, String password) throws SQLException {
      return delegate.getConnection(username, password);
    }

    @Override
    public java.io.PrintWriter getLogWriter() {
      return null;
    }

    @Override
    public void setLogWriter(java.io.PrintWriter out) {}

    @Override
    public void setLoginTimeout(int seconds) {}

    @Override
    public int getLoginTimeout() {
      return 0;
    }

    @Override
    public java.util.logging.Logger getParentLogger() {
      return java.util.logging.Logger.getLogger(InMemoryDataSource.class.getName());
    }

    @Override
    public <T> T unwrap(Class<T> iface) throws SQLException {
      throw new SQLException("Not a wrapper");
    }

    @Override
    public boolean isWrapperFor(Class<?> iface) {
      return false;
    }

    public void close() throws SQLException {
      try (Connection conn = getConnection();
          Statement stmt = conn.createStatement()) {
        stmt.execute("SHUTDOWN");
      }
    }
  }
}
