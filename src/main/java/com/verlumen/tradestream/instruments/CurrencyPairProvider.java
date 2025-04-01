package com.verlumen.tradestream.instruments;

import static com.google.common.collect.Streams.stream;

import com.google.common.collect.ImmutableList;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.http.HttpClient;
import java.io.IOException;
import java.io.Serializable;
import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;

final class CurrencyPairProvider implements Serializable, Provider<ImmutableList<CurrencyPair>> {
    private final CoinMarketCapConfig coinMarketCapConfig;
    private final HttpClient httpClient;

    @Inject
    CurrencyPairSupplyProvider(CoinMarketCapConfig coinMarketCapConfig, HttpClient httpClient) {
        this.coinMarketCapConfig = coinMarketCapConfig;
        this.httpClient = httpClient;
    }

    @Override
    public ImmutableList<CurrencyPair> get() {
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

            biStream(obj -> obj.get("symbol"), stream(dataElement.getAsJsonArray()).map(node -> node.getAsJsonObject()))
                .mapValues(obj -> obj.get("quote"))
                .filter((symbolElement, quoteElement) -> 
                        Stream.of(symbolElement, quoteElement)
                        .allMatch(element -> element != null && !element.isJsonNull()))
                .filterValues(quoteElement ->  quoteElement.isJsonObject())
                .mapKeys(JsonElement::getAsString)
                .mapValues(JsonElement::getAsJsonObject)
                .mapValues(quoteObj -> quoteObj.get("USD"))
                .filterValues(usdQuoteObj -> )
                .mapToObj((symbol, usdQuoteObj) -> usdQuoteObj.get("market_cap") != null && !usdQuoteObj.get("market_cap").isJsonNull())
            dataElement.getAsJsonArray().forEach(currencyNode -> {
                // JsonObject currencyObj = currencyNode.getAsJsonObject();
                // JsonElement symbolElement = currencyObj.get("symbol");
                // if (symbolElement == null || symbolElement.isJsonNull()) {
                //     return; // Skip if symbol is missing
                // }
                // String symbol = symbolElement.getAsString();

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

            return CurrencyPairSupplyImpl.create(listBuilder.build());
        } catch (IOException e) {
            // Handle exceptions
            throw new RuntimeException("Failed to fetch currency data", e);
        } catch (Exception e) {
            // Catch other parsing exceptions
            throw new RuntimeException("Error parsing currency data", e);
        }
    }
}
