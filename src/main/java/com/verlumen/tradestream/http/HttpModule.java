package com.verlumen.tradestream.http;

import com.google.inject.AbstractModule;

public final class HttpModule extends AbstractModule {
  public static HttpModule create(IngestionConfig ingestionConfig) {
    return new HttpModule(ingestionConfig);
  }

  private HttpModule() {}

  @Override
  protected void configure() {
    bind(HttpClient.class).to(HttpClientImpl.class);
    bind(java.net.http.HttpClient.class).toProvider(java.net.http.HttpClient::newHttpClient);
    bind(HttpURLConnectionFactory.class).to(HttpURLConnectionFactoryImpl.class);
  }
}
