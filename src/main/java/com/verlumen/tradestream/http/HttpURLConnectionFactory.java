package com.verlumen.tradestream.http;

import java.io.IOException;
import java.io.Serializable;
import java.net.HttpURLConnection;

public interface HttpURLConnectionFactory extends Serializable {
  HttpURLConnection create(String url) throws IOException;
}
