package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;

interface HttpURLConnectionFactory {
  String create(String url) throws IOException;
}
