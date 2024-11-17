package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;

import java.util.Properties;

final class KafkaProducerPropertiesProvider impements Provider<Properties> {
  private final Properties properties;

  @Inject
  KafkaProducerProperties(Properties properties) {
    this.properties = properties;
  }
}
