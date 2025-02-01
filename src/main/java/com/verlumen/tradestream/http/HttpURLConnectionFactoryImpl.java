package com.verlumen.tradestream.http;

import com.google.inject.Inject;

import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;

final class HttpURLConnectionFactoryImpl implements HttpURLConnectionFactory {
  @Inject
  HttpURLConnectionFactoryImpl() {}

  @Override
  public HttpURLConnection create(String url) throws IOException {
    return (HttpURLConnection) new URL(url).openConnection();
  }
}
