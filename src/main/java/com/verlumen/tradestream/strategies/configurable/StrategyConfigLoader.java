package com.verlumen.tradestream.strategies.configurable;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.yaml.snakeyaml.Yaml;

/** Utility class for loading strategy configurations from JSON and YAML files. */
public final class StrategyConfigLoader {

  /**
   * Enum representing all available strategy configurations. Each constant maps to a YAML resource
   * file in the strategies directory.
   */
  public enum ConfigStrategy {
    ADX_DMI("strategies/adx_dmi.yaml"),
    ADX_STOCHASTIC("strategies/adx_stochastic.yaml"),
    AROON_MFI("strategies/aroon_mfi.yaml"),
    ATR_CCI("strategies/atr_cci.yaml"),
    AWESOME_OSCILLATOR("strategies/awesome_oscillator.yaml"),
    BBAND_WILLIAMS_R("strategies/bband_williams_r.yaml"),
    CHAIKIN_OSCILLATOR("strategies/chaikin_oscillator.yaml"),
    CMF_ZERO_LINE("strategies/cmf_zero_line.yaml"),
    CMO_MFI("strategies/cmo_mfi.yaml"),
    DEMA_TEMA_CROSSOVER("strategies/dema_tema_crossover.yaml"),
    DONCHIAN_BREAKOUT("strategies/donchian_breakout.yaml"),
    DOUBLE_EMA_CROSSOVER("strategies/double_ema_crossover.yaml"),
    ELDER_RAY_MA("strategies/elder_ray_ma.yaml"),
    EMA_MACD("strategies/ema_macd.yaml"),
    KLINGER_VOLUME("strategies/klinger_volume.yaml"),
    MACD_CROSSOVER("strategies/macd_crossover.yaml"),
    MASS_INDEX("strategies/mass_index.yaml"),
    MOMENTUM_SMA_CROSSOVER("strategies/momentum_sma_crossover.yaml"),
    OBV_EMA("strategies/obv_ema.yaml"),
    PRICE_GAP("strategies/price_gap.yaml"),
    ROC_MA_CROSSOVER("strategies/roc_ma_crossover.yaml"),
    RSI_EMA_CROSSOVER("strategies/rsi_ema_crossover.yaml"),
    SMA_EMA_CROSSOVER("strategies/sma_ema_crossover.yaml"),
    STOCHASTIC_RSI("strategies/stochastic_rsi.yaml"),
    TRIPLE_EMA_CROSSOVER("strategies/triple_ema_crossover.yaml");

    private final String resourcePath;

    ConfigStrategy(String resourcePath) {
      this.resourcePath = resourcePath;
    }

    /**
     * Loads and returns the strategy configuration for this enum constant.
     *
     * @return The loaded StrategyConfig
     */
    public StrategyConfig get() {
      return loadResource(resourcePath);
    }

    /**
     * Returns the resource path for this strategy configuration.
     *
     * @return The classpath resource path
     */
    public String getResourcePath() {
      return resourcePath;
    }
  }

  private static final Gson GSON =
      new GsonBuilder()
          .registerTypeAdapter(ParameterType.class, new ParameterTypeAdapter())
          .setPrettyPrinting()
          .create();

  private static final Yaml YAML = new Yaml();

  private StrategyConfigLoader() {}

  /**
   * Loads a strategy configuration from a JSON file.
   *
   * @param path The path to the JSON file
   * @return The loaded strategy configuration
   */
  public static StrategyConfig loadJson(String path) {
    try {
      String content = Files.readString(Path.of(path), StandardCharsets.UTF_8);
      return parseJson(content);
    } catch (IOException e) {
      throw new RuntimeException("Failed to load JSON config from: " + path, e);
    }
  }

  /**
   * Loads a strategy configuration from a YAML file.
   *
   * @param path The path to the YAML file
   * @return The loaded strategy configuration
   */
  public static StrategyConfig loadYaml(String path) {
    try {
      String content = Files.readString(Path.of(path), StandardCharsets.UTF_8);
      return parseYaml(content);
    } catch (IOException e) {
      throw new RuntimeException("Failed to load YAML config from: " + path, e);
    }
  }

  /**
   * Loads a strategy configuration from a file, auto-detecting format based on extension.
   *
   * @param path The path to the config file (.json or .yaml/.yml)
   * @return The loaded strategy configuration
   */
  public static StrategyConfig load(String path) {
    String lowerPath = path.toLowerCase();
    if (lowerPath.endsWith(".yaml") || lowerPath.endsWith(".yml")) {
      return loadYaml(path);
    } else if (lowerPath.endsWith(".json")) {
      return loadJson(path);
    } else {
      throw new IllegalArgumentException(
          "Unsupported file format. Use .json, .yaml, or .yml: " + path);
    }
  }

  /**
   * Loads a strategy configuration from a JSON resource on the classpath.
   *
   * @param resourcePath The classpath resource path
   * @return The loaded strategy configuration
   */
  public static StrategyConfig loadJsonResource(String resourcePath) {
    try (InputStream is = StrategyConfigLoader.class.getResourceAsStream(resourcePath);
        Reader reader = new InputStreamReader(is, StandardCharsets.UTF_8)) {
      return GSON.fromJson(reader, StrategyConfig.class);
    } catch (IOException | NullPointerException e) {
      throw new RuntimeException("Failed to load JSON config from resource: " + resourcePath, e);
    }
  }

  /**
   * Loads a strategy configuration from a YAML resource on the classpath.
   *
   * @param resourcePath The classpath resource path
   * @return The loaded strategy configuration
   */
  public static StrategyConfig loadYamlResource(String resourcePath) {
    try (InputStream is = StrategyConfigLoader.class.getResourceAsStream(resourcePath)) {
      if (is == null) {
        throw new RuntimeException("Resource not found: " + resourcePath);
      }
      Map<String, Object> yamlMap = YAML.load(is);
      String json = GSON.toJson(yamlMap);
      return GSON.fromJson(json, StrategyConfig.class);
    } catch (IOException e) {
      throw new RuntimeException("Failed to load YAML config from resource: " + resourcePath, e);
    }
  }

  /**
   * Loads a strategy configuration from a resource, auto-detecting format based on extension.
   *
   * @param resourcePath The classpath resource path (.json or .yaml/.yml)
   * @return The loaded strategy configuration
   */
  public static StrategyConfig loadResource(String resourcePath) {
    String lowerPath = resourcePath.toLowerCase();
    if (lowerPath.endsWith(".yaml") || lowerPath.endsWith(".yml")) {
      return loadYamlResource(resourcePath);
    } else if (lowerPath.endsWith(".json")) {
      return loadJsonResource(resourcePath);
    } else {
      throw new IllegalArgumentException(
          "Unsupported file format. Use .json, .yaml, or .yml: " + resourcePath);
    }
  }

  /**
   * Parses a strategy configuration from a JSON string.
   *
   * @param jsonContent The JSON content
   * @return The parsed strategy configuration
   */
  public static StrategyConfig parseJson(String jsonContent) {
    return GSON.fromJson(jsonContent, StrategyConfig.class);
  }

  /**
   * Parses a strategy configuration from a YAML string.
   *
   * @param yamlContent The YAML content
   * @return The parsed strategy configuration
   */
  public static StrategyConfig parseYaml(String yamlContent) {
    Map<String, Object> yamlMap = YAML.load(yamlContent);
    String json = GSON.toJson(yamlMap);
    return GSON.fromJson(json, StrategyConfig.class);
  }

  /**
   * Loads all strategy configurations from a directory (JSON and YAML files).
   *
   * @param directoryPath The path to the directory
   * @return List of loaded strategy configurations
   */
  public static List<StrategyConfig> loadAll(String directoryPath) {
    List<StrategyConfig> configs = new ArrayList<>();

    try {
      Files.list(Path.of(directoryPath))
          .filter(Files::isRegularFile)
          .forEach(
              path -> {
                String fileName = path.getFileName().toString().toLowerCase();
                if (fileName.endsWith(".json")) {
                  configs.add(loadJson(path.toString()));
                } else if (fileName.endsWith(".yaml") || fileName.endsWith(".yml")) {
                  configs.add(loadYaml(path.toString()));
                }
              });
    } catch (IOException e) {
      throw new RuntimeException("Failed to load configs from directory: " + directoryPath, e);
    }

    return configs;
  }

  /**
   * Serializes a strategy configuration to JSON.
   *
   * @param config The strategy configuration
   * @return The JSON string
   */
  public static String toJson(StrategyConfig config) {
    return GSON.toJson(config);
  }

  /**
   * Saves a strategy configuration to a JSON file.
   *
   * @param config The strategy configuration
   * @param path The path to save to
   */
  public static void saveJson(StrategyConfig config, String path) {
    try {
      Files.writeString(Path.of(path), toJson(config), StandardCharsets.UTF_8);
    } catch (IOException e) {
      throw new RuntimeException("Failed to save JSON config to: " + path, e);
    }
  }

  /** Type adapter for ParameterType enum to handle case-insensitive parsing. */
  private static class ParameterTypeAdapter
      implements com.google.gson.JsonDeserializer<ParameterType>,
          com.google.gson.JsonSerializer<ParameterType> {

    @Override
    public ParameterType deserialize(
        com.google.gson.JsonElement json,
        java.lang.reflect.Type typeOfT,
        com.google.gson.JsonDeserializationContext context)
        throws com.google.gson.JsonParseException {
      String value = json.getAsString().toUpperCase();
      return ParameterType.valueOf(value);
    }

    @Override
    public com.google.gson.JsonElement serialize(
        ParameterType src,
        java.lang.reflect.Type typeOfSrc,
        com.google.gson.JsonSerializationContext context) {
      return new com.google.gson.JsonPrimitive(src.name());
    }
  }
}
