package com.verlumen.tradestream.instruments

import com.google.common.base.Supplier
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.google.inject.Inject
import com.verlumen.tradestream.http.HttpClient
import org.slf4j.LoggerFactory
import java.io.IOException
import java.io.Serializable

internal class CurrencyPairSupplier @Inject constructor(
    private val coinMarketCapConfig: CoinMarketCapConfig,
    private val httpClient: HttpClient
) : Serializable, Supplier<@JvmSuppressWildcards List<CurrencyPair>> {
    
    companion object {
        private val logger = LoggerFactory.getLogger(CurrencyPairSupplier::class.java)
        
        // Default pairs to use if API fails
        private val DEFAULT_PAIRS = listOf(
            "BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD", "XRP/USD"
        ).map { CurrencyPair.fromSymbol(it) }
    }
    
    override fun get(): List<CurrencyPair> {
        val url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        
        try {
            val apiKey = coinMarketCapConfig.apiKey()
            logger.info("Fetching currency pairs from CoinMarketCap. API Key: ${if (apiKey.isNullOrBlank()) "MISSING" else "****" + apiKey.takeLast(4)}") 
            
            // Check API key first
            if (apiKey.isNullOrBlank() || apiKey == "INVALID_API_KEY") {
                logger.warn("Invalid or missing CoinMarketCap API key. Using default currency pairs.")
                return DEFAULT_PAIRS
            }
            
            val parameters = "start=1&limit=${coinMarketCapConfig.topN()}&convert=USD"
            val fullUrl = "$url?$parameters"

            // Set the headers
            val headers = mapOf(
                "X-CMC_PRO_API_KEY" to apiKey,
                "Accept" to "application/json"
            )

            logger.info("Making API request to CoinMarketCap: $url (with params)")
            val responseStr = httpClient.get(fullUrl, headers)
            logger.info("Received response from CoinMarketCap")

            // Parse JSON response
            val rootNode = JsonParser.parseString(responseStr).asJsonObject
            
            // Check for error response
            if (rootNode.has("status")) {
                val status = rootNode.getAsJsonObject("status")
                if (status.has("error_code") && status.get("error_code").asInt != 0) {
                    val errorMessage = status.get("error_message")?.asString ?: "Unknown error"
                    logger.error("CoinMarketCap API error: $errorMessage")
                    return DEFAULT_PAIRS
                }
            }
            
            val dataElement = rootNode.get("data") ?: throw IOException("Missing data in response")

            if (!dataElement.isJsonArray) {
                logger.error("Invalid response format from CoinMarketCap API")
                return DEFAULT_PAIRS
            }

            // Convert to list of currency pairs
            val pairs = dataElement.asJsonArray
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
                
            logger.info("Retrieved ${pairs.size} currency pairs from CoinMarketCap")
            
            // If we got no pairs, use defaults
            return if (pairs.isEmpty()) {
                logger.warn("No currency pairs returned from API. Using defaults.")
                DEFAULT_PAIRS
            } else {
                pairs
            }
                
        } catch (e: IOException) {
            logger.error("Failed to fetch currency data: ${e.message}", e)
            return DEFAULT_PAIRS
        } catch (e: Exception) {
            logger.error("Error parsing currency data: ${e.message}", e)
            return DEFAULT_PAIRS
        }
    }
}
