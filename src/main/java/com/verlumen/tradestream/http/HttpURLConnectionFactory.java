package com.verlumen.tradestream.http;

import java.io.IOException;
import java.net.HttpURLConnection;

public interface HttpURLConnectionFactory {
  HttpURLConnection create(String url) throws IOException;
}
