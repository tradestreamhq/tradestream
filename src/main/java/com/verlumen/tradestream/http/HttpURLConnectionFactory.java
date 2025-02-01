package com.verlumen.tradestream.ingestion;

import java.io.IOException;
import java.net.HttpURLConnection;

public interface HttpURLConnectionFactory {
  HttpURLConnection create(String url) throws IOException;
}
