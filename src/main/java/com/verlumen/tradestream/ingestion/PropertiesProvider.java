package com.verlumen.tradestream.ingestion;

import com.google.devtools.build.runfiles.Runfiles;
import com.google.inject.Inject;
import com.google.inject.Provider;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.Properties;

final class PropertiesProvider implements Provider<Properties> {
  private static final String CONFIG_FILE_PATH = "src/main/java/com/verlumen/tradestream/ingestion/config.properties";
  private static final String WORKSPACE_NAME = "tradestream";

  @Inject
  PropertiesProvider() {}

  @Override
  public Properties get() {
    try {
      // Step 1: Preload Runfiles
      Runfiles.Preloaded runfilesPreloaded = Runfiles.preload();

      // Resolve the path to the properties file in the runfiles directory
      String propertiesPath = runfilesPreloaded.unmapped()
        .rlocation(WORKSPACE_NAME + "/" + CONFIG_FILE_PATH);

      // Step 2: Load properties from the file
      Properties props = new Properties();
      try (FileInputStream inputStream = new FileInputStream(propertiesPath)) {
        props.load(inputStream);
      }
      return props;
    } catch (IOException e) {
      throw new RuntimeException("Failed to load properties file", e);
    }
  }
}
