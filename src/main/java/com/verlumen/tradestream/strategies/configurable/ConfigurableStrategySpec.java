package com.verlumen.tradestream.strategies.configurable;

import com.verlumen.tradestream.strategies.StrategySpec;

/**
 * A StrategySpec that wraps config-based factory and param config. Drop-in replacement for
 * hardcoded StrategySpec instances.
 */
public final class ConfigurableStrategySpec {

  private final StrategyConfig config;
  private final StrategySpec strategySpec;

  public ConfigurableStrategySpec(StrategyConfig config) {
    this.config = config;
    this.strategySpec =
        new StrategySpec(
            new ConfigurableParamConfig(config), new ConfigurableStrategyFactory(config));
  }

  public static ConfigurableStrategySpec fromJson(String jsonPath) {
    StrategyConfig config = StrategyConfigLoader.loadJson(jsonPath);
    return new ConfigurableStrategySpec(config);
  }

  public static ConfigurableStrategySpec fromConfig(StrategyConfig config) {
    return new ConfigurableStrategySpec(config);
  }

  public StrategyConfig getConfig() {
    return config;
  }

  public StrategySpec getStrategySpec() {
    return strategySpec;
  }

  public ConfigurableParamConfig getParamConfig() {
    return (ConfigurableParamConfig) strategySpec.getParamConfig();
  }

  public ConfigurableStrategyFactory getStrategyFactory() {
    return (ConfigurableStrategyFactory) strategySpec.getStrategyFactory();
  }
}
