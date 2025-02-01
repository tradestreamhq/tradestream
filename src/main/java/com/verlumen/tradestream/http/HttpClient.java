package com.verlumen.tradestream.http;

import java.io.IOException;
import java.util.Map;

public interface HttpClient {
    String get(String url, Map<String, String> headers) throws IOException;
}
