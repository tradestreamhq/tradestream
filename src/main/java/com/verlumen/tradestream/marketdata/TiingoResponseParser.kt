package com.verlumen.tradestream.marketdata

import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonParser
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException

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
    fun parseCandles(
        jsonResponse: String,
        currencyPair: String,
    ): List<Candle> {
        return try {
            val jsonElement = JsonParser.parseString(jsonResponse)
            // Tiingo returns an array, sometimes empty, sometimes containing one object per ticker.
            // We expect only one object since we query one ticker at a time.
            if (jsonElement.isJsonArray && !jsonElement.asJsonArray.isEmpty) {
                val tickerData = jsonElement.asJsonArray[0]?.asJsonObject ?: return emptyList() // Handle potential null element
                val priceDataArray = tickerData.getAsJsonArray("priceData")
                if (priceDataArray != null) {
                    parsePriceDataArray(priceDataArray, currencyPair)
                } else {
                    println("Warning: Missing 'priceData' array in Tiingo response for $currencyPair")
                    emptyList()
                }
            } else {
                if (jsonElement.isJsonArray && jsonElement.asJsonArray.isEmpty) {
                    println("Info: Received empty array from Tiingo for $currencyPair")
                } else {
                    println("Warning: Unexpected Tiingo response format (not a non-empty array) for $currencyPair: $jsonResponse")
                }
                emptyList()
            }
        } catch (e: Exception) {
            println("Error parsing Tiingo JSON response for $currencyPair: ${e.message}")
            emptyList()
        }
    }

    private fun parsePriceDataArray(
        priceDataArray: JsonArray,
        currencyPair: String,
    ): List<Candle> {
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

    private fun parseCandleElement(
        element: JsonElement,
        currencyPair: String,
    ): Candle? {
        if (!element.isJsonObject) return null
        val candleJson = element.asJsonObject

        // Use safe extraction with default fallback or early return
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
            .setCurrencyPair(currencyPair)
            .setOpen(open)
            .setHigh(high)
            .setLow(low)
            .setClose(close)
            .setVolume(volume)
            .build()
    }

    private fun parseTimestamp(dateString: String): Timestamp? {
        return try {
            // Parse using java.time for better timezone handling
            val odt = OffsetDateTime.parse(dateString, TIINGO_DATE_FORMATTER)
            val instant = odt.toInstant() // Convert to java.time.Instant
            Timestamps.fromMillis(instant.toEpochMilli()) // Convert to Protobuf Timestamp
        } catch (e: DateTimeParseException) {
            println("Error parsing Tiingo timestamp: $dateString - ${e.message}")
            null
        }
    }
}
