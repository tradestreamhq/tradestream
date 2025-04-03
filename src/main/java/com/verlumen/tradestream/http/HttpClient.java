package com.verlumen.tradestream.http;

import java.io.IOException;
import java.io.Serializable;
import java.util.Map;

public interface HttpClient extends Serializable {
    String get(String url, Map<String, String> headers) throws IOException;
}
