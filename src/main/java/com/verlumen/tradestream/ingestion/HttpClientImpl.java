package com.verlumen.tradestream.ingestion;

import com.google.inject.Inject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;

final class HttpClientImpl implements HttpClient {
    private final HttpURLConnectionFactory hHttpURLConnectionFactory;

    @Inject
    HttpClientImpl(HttpURLConnectionFactory hHttpURLConnectionFactory) {
        this.httpURLConnectionFactory = hHttpURLConnectionFactory;
    }

    @Override
    public String get(String url, Map<String, String> headers) throws IOException {
        HttpURLConnection con = httpURLConnectionFactory.create(url);
        con.setRequestMethod("GET");
        for (Map.Entry<String, String> header : headers.entrySet()) {
            con.setRequestProperty(header.getKey(), header.getValue());
        }

        int responseCode = con.getResponseCode();
        if (responseCode != HttpURLConnection.HTTP_OK) {
            throw new IOException(
                "Failed to fetch data: HTTP code " + responseCode);
        }

        BufferedReader in =
            new BufferedReader(new InputStreamReader(con.getInputStream()));
        String inputLine;
        StringBuilder responseStrBuilder = new StringBuilder();

        while ((inputLine = in.readLine()) != null) {
            responseStrBuilder.append(inputLine);
        }
        in.close();

        return responseStrBuilder.toString();
    }
}
