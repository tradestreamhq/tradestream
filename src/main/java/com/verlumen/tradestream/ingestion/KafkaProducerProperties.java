package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;
import com.google.inject.Provider;

final class KafkaProducerPropertiesProvider impements Provider<Properties> {
  private final Properties properties;

  @Inject
  KafkaProducerProperties(Properties properties) {
    this.properties = properties;
  }
}
