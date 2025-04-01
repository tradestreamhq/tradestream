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

            return biStream(obj -> obj.get("symbol"), stream(dataElement.getAsJsonArray()).map(node -> node.getAsJsonObject()))
                .mapValues(obj -> obj.get("quote"))
                .filter((symbolElement, quoteElement) -> 
                        Stream.of(symbolElement, quoteElement)
                        .allMatch(element -> element != null && !element.isJsonNull()))
                .filterValues(quoteElement ->  quoteElement.isJsonObject())
                .mapKeys(JsonElement::getAsString)
                .mapValues(JsonElement::getAsJsonObject)
                .mapValues(quoteObj -> quoteObj.get("USD"))
                .filterValues(usdQuoteObj ->
                      usdQuoteObj.get("market_cap") != null && !usdQuoteObj.get("market_cap").isJsonNull())
                .mapToObj((baseCurrency, unused) -> baseCurrency + "/USD")
                .distinct()
                .map(CurrencyPair::fromSymbol)
                .collect(toImmutableList());
        } catch (IOException e) {
            // Handle exceptions
            throw new RuntimeException("Failed to fetch currency data", e);
        } catch (Exception e) {
            // Catch other parsing exceptions
            throw new RuntimeException("Error parsing currency data", e);
        }
    }
}
