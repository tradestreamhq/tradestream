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

/** Utility class for loading strategy configurations from JSON files. */
public final class StrategyConfigLoader {

  private static final Gson GSON =
      new GsonBuilder()
          .registerTypeAdapter(ParameterType.class, new ParameterTypeAdapter())
          .setPrettyPrinting()
          .create();

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
   * Parses a strategy configuration from a JSON string.
   *
   * @param jsonContent The JSON content
   * @return The parsed strategy configuration
   */
  public static StrategyConfig parseJson(String jsonContent) {
    return GSON.fromJson(jsonContent, StrategyConfig.class);
  }

  /**
   * Loads all strategy configurations from a directory (JSON files only).
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
