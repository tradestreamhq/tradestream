package com.verlumen.tradestream.marketdata

import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import java.time.Instant
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter

/**
 * Parses JSON responses from the Tiingo Crypto Price API.
 * [https://api.tiingo.com/documentation/crypto](https://api.tiingo.com/documentation/crypto)
 */
object TiingoResponseParser {
    // Tiingo uses ISO 8601 format with offset, e.g., "2019-01-02T00:00:00+00:00"
    private val TIINGO_DATE_FORMATTER = DateTimeFormatter.ISO_OFFSET_DATE_TIME

    /**
     * Parses the JSON response string into a list of Candle objects.
     *
     * @param jsonResponse The JSON string received from the Tiingo API.
     * @param currencyPair The currency pair associated with this response (e.g., "BTC/USD").
     * @return A list of Candle objects parsed from the response. Returns an empty list
     * if the response is invalid or contains no candle data.
     */
    fun parseCandles(jsonResponse: String, currencyPair: String): List<Candle> {
        return try {
            val jsonElement = JsonParser.parseString(jsonResponse)
            // Tiingo returns an array, sometimes empty, sometimes containing one object per ticker.
            // We expect only one object since we query one ticker at a time.
            if (jsonElement.isJsonArray && !jsonElement.asJsonArray.isEmpty) {
                val tickerData = jsonElement.asJsonArray[0].asJsonObject
                val priceDataArray = tickerData.getAsJsonArray("priceData")
                if (priceDataArray != null) {
                    parsePriceDataArray(priceDataArray, currencyPair)
                } else {
                    // Handle cases where "priceData" might be missing or null
                    emptyList()
                }
            } else {
                // Handle empty array or non-array response
                emptyList()
            }
        } catch (e: Exception) {
            // Log parsing errors appropriately in a real scenario
            println("Error parsing Tiingo response for $currencyPair: ${e.message}")
            emptyList()
        }
    }

    private fun parsePriceDataArray(priceDataArray: JsonArray, currencyPair: String): List<Candle> {
        val candles = mutableListOf<Candle>()
        for (element in priceDataArray) {
            try {
                parseCandleElement(element, currencyPair)?.let { candles.add(it) }
            } catch (e: Exception) {
                println("Error parsing individual candle element for $currencyPair: ${e.message}, Element: $element")
                // Continue parsing other elements
            }
        }
        // Sort candles by timestamp ascending, as Tiingo might not guarantee order
        candles.sortBy { Timestamps.toMillis(it.timestamp) }
        return candles
    }

    private fun parseCandleElement(element: JsonElement, currencyPair: String): Candle? {
        if (!element.isJsonObject) return null
        val candleJson = element.asJsonObject

        // Safely extract fields, returning null if any required field is missing/invalid
        val dateString = candleJson.getAsJsonPrimitive("date")?.asString ?: return null
        val open = candleJson.getAsJsonPrimitive("open")?.asDouble ?: return null
        val high = candleJson.getAsJsonPrimitive("high")?.asDouble ?: return null
        val low = candleJson.getAsJsonPrimitive("low")?.asDouble ?: return null
        val close = candleJson.getAsJsonPrimitive("close")?.asDouble ?: return null
        val volume = candleJson.getAsJsonPrimitive("volume")?.asDouble ?: return null
        // volumeNotional is also available if needed

        val timestamp = parseTimestamp(dateString) ?: return null

        return Candle.newBuilder()
            .setTimestamp(timestamp)
            .setCurrencyPair(currencyPair) // Set the currency pair
            .setOpen(open)
            .setHigh(high)
            .setLow(low)
            .setClose(close)
            .setVolume(volume)
            .build()
    }

    private fun parseTimestamp(dateString: String): Timestamp? {
        return try {
            val odt = OffsetDateTime.parse(dateString, TIINGO_DATE_FORMATTER)
            val instant = odt.toInstant()
            Timestamps.fromMillis(instant.toEpochMilli())
        } catch (e: Exception) {
            println("Error parsing Tiingo timestamp: $dateString - ${e.message}")
            null
        }
    }
}
