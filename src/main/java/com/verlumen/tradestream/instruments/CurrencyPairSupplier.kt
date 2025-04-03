package com.verlumen.tradestream.instruments

import com.google.common.base.Supplier
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.google.inject.Inject
import com.verlumen.tradestream.http.HttpClient
import java.io.IOException
import java.io.Serializable

internal class CurrencyPairSupplier @Inject constructor(
    private val coinMarketCapConfig: CoinMarketCapConfig,
    private val httpClient: HttpClient
) : Serializable, Supplier<@JvmSuppressWildcards List<CurrencyPair>> {
    override fun get(): List<CurrencyPair> {
        val url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        
        try {
            val parameters = "start=1&limit=${coinMarketCapConfig.topN()}&convert=USD"
            val fullUrl = "$url?$parameters"

            // Set the headers
            val headers = mapOf(
                "X-CMC_PRO_API_KEY" to coinMarketCapConfig.apiKey(),
                "Accept" to "application/json"
            )

            val responseStr = httpClient.get(fullUrl, headers)

            // Parse JSON response
            val rootNode = JsonParser.parseString(responseStr).asJsonObject
            val dataElement = rootNode.get("data") ?: throw IOException("Missing data in response")

            if (!dataElement.isJsonArray) {
                throw IOException("Invalid response format from CoinMarketCap API")
            }

            // Convert to list of currency pairs
            return dataElement.asJsonArray
                .mapNotNull { it.asJsonObject }
                .mapNotNull { currencyObj ->
                    val symbol = currencyObj.get("symbol")?.takeIf { !it.isJsonNull }?.asString ?: return@mapNotNull null
                    val quoteObj = currencyObj.get("quote")?.takeIf { it.isJsonObject }?.asJsonObject ?: return@mapNotNull null
                    val usdQuoteObj = quoteObj.get("USD")?.takeIf { it.isJsonObject }?.asJsonObject ?: return@mapNotNull null
                    
                    // Check for market cap
                    if (usdQuoteObj.has("market_cap") && !usdQuoteObj.get("market_cap").isJsonNull) {
                        "$symbol/USD"
                    } else null
                }
                .distinct()
                .map { CurrencyPair.fromSymbol(it) }
                
        } catch (e: IOException) {
            throw RuntimeException("Failed to fetch currency data", e)
        } catch (e: Exception) {
            throw RuntimeException("Error parsing currency data", e)
        }
    }
}
