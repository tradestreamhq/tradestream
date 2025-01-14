package com.verlumen.tradestream.ingestion;

import java.io.IOException;
import java.net.HttpURLConnection;

interface HttpURLConnectionFactory {
  HttpURLConnection create(String url) throws IOException;
}
