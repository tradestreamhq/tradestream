package com.verlumen.tradestream.http;

import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import com.verlumen.tradestream.http.HttpURLConnectionFactory;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;

final class HttpClientImpl implements HttpClient {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    private final HttpURLConnectionFactory httpURLConnectionFactory;

    @Inject
    HttpClientImpl(HttpURLConnectionFactory httpURLConnectionFactory) {
        logger.atInfo().log("Initializing HttpClient");
        this.httpURLConnectionFactory = httpURLConnectionFactory;
        logger.atInfo().log("HttpClient initialization complete");
    }

    @Override
    public String get(String url, Map<String, String> headers) throws IOException {
        logger.atInfo().log("Making GET request to URL: %s", url);
        logger.atFine().log("Request headers: %s", headers);

        HttpURLConnection con = null;
        try {
            logger.atFine().log("Creating HTTP connection...");
            con = httpURLConnectionFactory.create(url);
            con.setRequestMethod("GET");
            
            logger.atFine().log("Setting request headers...");
            for (Map.Entry<String, String> header : headers.entrySet()) {
                logger.atFine().log("Setting header: %s = %s", header.getKey(), header.getValue());
                con.setRequestProperty(header.getKey(), header.getValue());
            }

            int responseCode = con.getResponseCode();
            logger.atInfo().log("Received response code: %d", responseCode);

            if (responseCode != HttpURLConnection.HTTP_OK) {
                String errorMessage = String.format("Failed to fetch data: HTTP code %d", responseCode);
                throw new IOException(errorMessage);
            }

            logger.atFine().log("Reading response...");
            BufferedReader in = new BufferedReader(new InputStreamReader(con.getInputStream()));
            String inputLine;
            StringBuilder responseStrBuilder = new StringBuilder();

            while ((inputLine = in.readLine()) != null) {
                responseStrBuilder.append(inputLine);
            }
            in.close();

            String response = responseStrBuilder.toString();
            logger.atFine().log("Response length: %d characters", response.length());
            logger.atInfo().log("Successfully completed GET request to %s", url);

            return response;
        } catch (IOException e) {
            logger.atSevere().withCause(e).log("Failed to execute GET request to %s", url);
            throw e;
        } finally {
            if (con != null) {
                logger.atFine().log("Disconnecting HTTP connection");
                con.disconnect();
            }
        }
    }
}
