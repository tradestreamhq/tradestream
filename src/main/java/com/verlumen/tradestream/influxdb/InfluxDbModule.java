package com.verlumen.tradestream.marketdata;

import com.google.auto.value.AutoValue;
import com.google.inject.AbstractModule;
import com.google.inject.Provides;
import com.google.inject.Singleton;
import com.influxdb.client.InfluxDBClient;
import com.influxdb.client.InfluxDBClientFactory;

@AutoValue
public abstract class InfluxDbModule extends AbstractModule {
  public static InfluxDbModule create(
      String influxDbUrl,
      String influxDbToken,
      String influxDbOrg,
      String influxDbBucket) {
    return new AutoValue_InfluxDbModule(
        influxDbUrl,
        influxDbToken,
        influxDbOrg,
        influxDbBucket);
  }

  abstract String influxDbUrl();

  abstract String influxDbToken();

  abstract String influxDbOrg();




  @Provides
  @Singleton
  InfluxDBClient provideInfluxDBClient() {
    return InfluxDBClientFactory.create(
        influxDbUrl(), influxDbToken().toCharArray(), influxDbOrg(), influxDbBucket());
  }
}
