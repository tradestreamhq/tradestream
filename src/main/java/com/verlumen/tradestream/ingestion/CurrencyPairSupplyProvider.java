package com.verlumen.tradestream.ingestion;

import com.google.common.collect.ImmutableList;
import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.http.HttpClient;
import java.io.IOException;
import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;

final class CurrencyPairSupplyProvider implements Provider<CurrencyPairSupply> {
    private final CoinMarketCapConfig coinMarketCapConfig;
    private final Gson gson;
    private final HttpClient httpClient;

    @Inject
    CurrencyPairSupplyProvider(CoinMarketCapConfig coinMarketCapConfig, Gson gson, HttpClient httpClient) {
        this.coinMarketCapConfig = coinMarketCapConfig;
        this.gson = gson;
        this.httpClient = httpClient;
    }

    @Override
    public CurrencyPairSupply get() {
        String url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest";
        try {
            String parameters = "start=1&limit=" + coinMarketCapConfig.topN() + "&convert=USD";
            String fullUrl = url + "?" + parameters;

            // Set the headers
            Map<String, String> headers = new HashMap<>();
            headers.put("X-CMC_PRO_API_KEY", coinMarketCapConfig.apiKey());
            headers.put("Accept", "application/json");

            String responseStr = httpClient.get(fullUrl, headers);

            // Parse JSON response using Gson
            JsonObject rootNode = JsonParser.parseString(responseStr).getAsJsonObject();
            JsonElement dataElement = rootNode.get("data");

            if (dataElement == null || !dataElement.isJsonArray()) {
                throw new IOException("Invalid response from CoinMarketCap API");
            }

            ImmutableList.Builder<CurrencyPairMetadata> listBuilder = ImmutableList.builder();

            dataElement.getAsJsonArray().forEach(currencyNode -> {
                JsonObject currencyObj = currencyNode.getAsJsonObject();
                JsonElement symbolElement = currencyObj.get("symbol");
                if (symbolElement == null || symbolElement.isJsonNull()) {
                    return; // Skip if symbol is missing
                }
                String symbol = symbolElement.getAsString();

                JsonElement quoteElement = currencyObj.get("quote");
                if (quoteElement == null || !quoteElement.isJsonObject()) {
                    return; // Skip if quote is missing
                }

                JsonObject quoteObj = quoteElement.getAsJsonObject();
                JsonElement usdQuoteElement = quoteObj.get("USD");
                if (usdQuoteElement == null || !usdQuoteElement.isJsonObject()) {
                    return; // Skip if USD quote is missing
                }

                JsonObject usdQuoteObj = usdQuoteElement.getAsJsonObject();
                JsonElement marketCapElement = usdQuoteObj.get("market_cap");
                if (marketCapElement == null || marketCapElement.isJsonNull()) {
                    return; // Skip if market_cap is missing
                }

                BigDecimal marketCap = marketCapElement.getAsBigDecimal();

                // Create pair string
                String pair = symbol + "/USD";

                // Create CurrencyPairMetadata
                CurrencyPairMetadata metadata = CurrencyPairMetadata.create(pair, marketCap);

                listBuilder.add(metadata);
            });

            return CurrencyPairSupply.create(listBuilder.build());
        } catch (IOException e) {
            // Handle exceptions
            throw new RuntimeException("Failed to fetch currency data", e);
        } catch (Exception e) {
            // Catch other parsing exceptions
            throw new RuntimeException("Error parsing currency data", e);
        }
    }
}
