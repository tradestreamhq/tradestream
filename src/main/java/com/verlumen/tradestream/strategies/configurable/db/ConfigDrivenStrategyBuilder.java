package com.verlumen.tradestream.strategies.configurable.db;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;
import com.verlumen.tradestream.strategies.configurable.ConditionConfig;
import com.verlumen.tradestream.strategies.configurable.ConfigurableStrategyFactory;
import com.verlumen.tradestream.strategies.configurable.IndicatorConfig;
import com.verlumen.tradestream.strategies.configurable.ParameterDefinition;
import com.verlumen.tradestream.strategies.configurable.StrategyConfig;
import java.lang.reflect.Type;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.logging.Level;
import java.util.logging.Logger;
import javax.sql.DataSource;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

/**
 * Reads strategy_specs rows from PostgreSQL and builds Ta4j strategies via
 * ConfigurableStrategyFactory. This is the database-driven counterpart to file-based config
 * loading.
 */
public final class ConfigDrivenStrategyBuilder {
  private static final Logger logger =
      Logger.getLogger(ConfigDrivenStrategyBuilder.class.getName());

  private static final Gson GSON = new GsonBuilder().create();

  private static final Type INDICATOR_LIST_TYPE =
      new TypeToken<List<IndicatorConfig>>() {}.getType();
  private static final Type CONDITION_LIST_TYPE =
      new TypeToken<List<ConditionConfig>>() {}.getType();
  private static final Type PARAMETER_LIST_TYPE =
      new TypeToken<List<ParameterDefinition>>() {}.getType();

  private static final String SELECT_ACTIVE_SPECS =
      "SELECT id, name, description, complexity, indicators, entry_conditions, "
          + "exit_conditions, parameters FROM strategy_specs WHERE is_active = true "
          + "ORDER BY name";

  private static final String SELECT_SPEC_BY_NAME =
      "SELECT id, name, description, complexity, indicators, entry_conditions, "
          + "exit_conditions, parameters FROM strategy_specs WHERE name = ? AND is_active = true";

  private final DataSource dataSource;

  public ConfigDrivenStrategyBuilder(DataSource dataSource) {
    this.dataSource = dataSource;
  }

  /** Loads all active strategy specs from the database and converts them to StrategyConfigs. */
  public List<StrategyConfig> loadAllSpecs() throws SQLException {
    List<StrategyConfig> configs = new ArrayList<>();
    try (Connection conn = dataSource.getConnection();
        PreparedStatement stmt = conn.prepareStatement(SELECT_ACTIVE_SPECS);
        ResultSet rs = stmt.executeQuery()) {
      while (rs.next()) {
        try {
          configs.add(mapRowToConfig(rs));
        } catch (Exception e) {
          logger.log(Level.WARNING, "Failed to parse strategy spec: " + rs.getString("name"), e);
        }
      }
    }
    return configs;
  }

  /** Loads a single strategy spec by name. */
  public Optional<StrategyConfig> loadSpec(String name) throws SQLException {
    try (Connection conn = dataSource.getConnection();
        PreparedStatement stmt = conn.prepareStatement(SELECT_SPEC_BY_NAME)) {
      stmt.setString(1, name);
      try (ResultSet rs = stmt.executeQuery()) {
        if (rs.next()) {
          return Optional.of(mapRowToConfig(rs));
        }
      }
    }
    return Optional.empty();
  }

  /**
   * Builds a Ta4j Strategy from a named strategy_spec in the database.
   *
   * @param specName the strategy_specs.name value
   * @param barSeries the bar series to build the strategy against
   * @return the built strategy, or empty if not found
   */
  public Optional<Strategy> buildStrategy(String specName, BarSeries barSeries) throws Exception {
    Optional<StrategyConfig> config = loadSpec(specName);
    if (config.isEmpty()) {
      return Optional.empty();
    }
    ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config.get());
    Strategy strategy = factory.createStrategy(barSeries, factory.getDefaultParameters());
    return Optional.of(strategy);
  }

  /**
   * Builds Ta4j Strategies for all active specs in the database.
   *
   * @param barSeries the bar series to build strategies against
   * @return list of named strategies
   */
  public List<NamedStrategy> buildAllStrategies(BarSeries barSeries) throws Exception {
    List<StrategyConfig> configs = loadAllSpecs();
    List<NamedStrategy> strategies = new ArrayList<>();
    for (StrategyConfig config : configs) {
      try {
        ConfigurableStrategyFactory factory = new ConfigurableStrategyFactory(config);
        Strategy strategy = factory.createStrategy(barSeries, factory.getDefaultParameters());
        strategies.add(new NamedStrategy(config.getName(), strategy, config));
      } catch (Exception e) {
        logger.log(Level.WARNING, "Failed to build strategy: " + config.getName(), e);
      }
    }
    return strategies;
  }

  private StrategyConfig mapRowToConfig(ResultSet rs) throws SQLException {
    String indicatorsJson = rs.getString("indicators");
    String entryJson = rs.getString("entry_conditions");
    String exitJson = rs.getString("exit_conditions");
    String parametersJson = rs.getString("parameters");

    List<IndicatorConfig> indicators = GSON.fromJson(indicatorsJson, INDICATOR_LIST_TYPE);
    List<ConditionConfig> entryConditions = GSON.fromJson(entryJson, CONDITION_LIST_TYPE);
    List<ConditionConfig> exitConditions = GSON.fromJson(exitJson, CONDITION_LIST_TYPE);
    List<ParameterDefinition> parameters = GSON.fromJson(parametersJson, PARAMETER_LIST_TYPE);

    return StrategyConfig.builder()
        .name(rs.getString("name"))
        .description(rs.getString("description"))
        .complexity(rs.getString("complexity"))
        .indicators(indicators)
        .entryConditions(entryConditions)
        .exitConditions(exitConditions)
        .parameters(parameters)
        .build();
  }

  /** A strategy paired with its name and source config. */
  public static final class NamedStrategy {
    private final String name;
    private final Strategy strategy;
    private final StrategyConfig config;

    public NamedStrategy(String name, Strategy strategy, StrategyConfig config) {
      this.name = name;
      this.strategy = strategy;
      this.config = config;
    }

    public String getName() {
      return name;
    }

    public Strategy getStrategy() {
      return strategy;
    }

    public StrategyConfig getConfig() {
      return config;
    }
  }
}
