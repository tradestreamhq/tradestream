package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.util.Timestamps
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import java.time.Instant // Use java.time

@RunWith(JUnit4::class)
class TiingoResponseParserTest {

    private val sampleJsonResponse = """
       [
         {
           "ticker": "btcusd",
           "baseCurrency": "btc",
           "quoteCurrency": "usd",
           "priceData": [
             {
               "date": "2023-10-26T00:00:00+00:00",
               "open": 34500.50,
               "high": 34800.75,
               "low": 34200.25,
               "close": 34650.00,
               "volume": 1500.5,
               "volumeNotional": 51990825.0,
               "tradesDone": 12000
             },
             {
               "date": "2023-10-27T00:00:00+00:00",
               "open": 34650.00,
               "high": 35000.00,
               "low": 34500.00,
               "close": 34950.80,
               "volume": 1800.2,
               "volumeNotional": 62917080.16,
               "tradesDone": 15000
             }
           ]
         }
       ]
    """.trimIndent()

    private val sampleSortedJsonResponse = """
       [
         {
           "ticker": "btcusd",
           "baseCurrency": "btc",
           "quoteCurrency": "usd",
           "priceData": [
              {
               "date": "2023-10-27T00:00:00+00:00",
               "open": 34650.00,
               "high": 35000.00,
               "low": 34500.00,
               "close": 34950.80,
               "volume": 1800.2
             },
             {
               "date": "2023-10-26T00:00:00+00:00",
               "open": 34500.50,
               "high": 34800.75,
               "low": 34200.25,
               "close": 34650.00,
               "volume": 1500.5
             }
           ]
         }
       ]
    """.trimIndent()


    private val sampleEmptyPriceDataJsonResponse = """
       [{"ticker": "btcusd", "priceData": [] }]
    """.trimIndent()

    private val sampleMissingPriceDataJsonResponse = """
       [{"ticker": "btcusd"}]
    """.trimIndent()

    private val sampleInvalidCandleJsonResponse = """
       [{"ticker": "btcusd", "priceData": [{"date": "2023-10-26T00:00:00+00:00" /* missing fields */ }]}]
    """.trimIndent()

    private val sampleEmptyArrayResponse = "[]"
    private val sampleInvalidJsonResponse = "[{\"ticker\": \"btcusd\",]" // Malformed JSON
    private val sampleNonArrayResponse = "{\"ticker\": \"btcusd\"}" // Object instead of array


    @Test
    fun `parseCandles parses valid response correctly`() {
        val candles = TiingoResponseParser.parseCandles(sampleJsonResponse, "BTC/USD")

        assertThat(candles).hasSize(2)

        val firstCandle = candles[0]
        assertThat(firstCandle.currencyPair).isEqualTo("BTC/USD")
        // Use java.time.Instant for comparison
        assertThat(Instant.ofEpochMilli(Timestamps.toMillis(firstCandle.timestamp)))
            .isEqualTo(Instant.parse("2023-10-26T00:00:00Z"))
        assertThat(firstCandle.open).isEqualTo(34500.50)
        assertThat(firstCandle.high).isEqualTo(34800.75)
        assertThat(firstCandle.low).isEqualTo(34200.25)
        assertThat(firstCandle.close).isEqualTo(34650.00)
        assertThat(firstCandle.volume).isEqualTo(1500.5)

        val secondCandle = candles[1]
        assertThat(secondCandle.currencyPair).isEqualTo("BTC/USD")
        assertThat(Instant.ofEpochMilli(Timestamps.toMillis(secondCandle.timestamp)))
             .isEqualTo(Instant.parse("2023-10-27T00:00:00Z"))
        assertThat(secondCandle.close).isEqualTo(34950.80)
    }

     @Test
    fun `parseCandles sorts candles by timestamp`() {
        val candles = TiingoResponseParser.parseCandles(sampleSortedJsonResponse, "BTC/USD") // Use out-of-order response

        assertThat(candles).hasSize(2)
        // Verify timestamps are sorted ascending
        assertThat(Timestamps.toMillis(candles[0].timestamp))
            .isEqualTo(Instant.parse("2023-10-26T00:00:00Z").toEpochMilli())
        assertThat(Timestamps.toMillis(candles[1].timestamp))
            .isEqualTo(Instant.parse("2023-10-27T00:00:00Z").toEpochMilli())
         // Verify content corresponds to sorted order
        assertThat(candles[0].close).isEqualTo(34650.00) // Candle from 26th
        assertThat(candles[1].close).isEqualTo(34950.80) // Candle from 27th
    }


    @Test
    fun `parseCandles returns empty list for empty priceData`() {
        val candles = TiingoResponseParser.parseCandles(sampleEmptyPriceDataJsonResponse, "BTC/USD")
        assertThat(candles).isEmpty()
    }

     @Test
    fun `parseCandles returns empty list for missing priceData`() {
        val candles = TiingoResponseParser.parseCandles(sampleMissingPriceDataJsonResponse, "BTC/USD")
        assertThat(candles).isEmpty()
    }

    @Test
    fun `parseCandles returns empty list for empty JSON array response`() {
        val candles = TiingoResponseParser.parseCandles(sampleEmptyArrayResponse, "BTC/USD")
        assertThat(candles).isEmpty()
    }

     @Test
    fun `parseCandles returns empty list for non array response`() {
        val candles = TiingoResponseParser.parseCandles(sampleNonArrayResponse, "BTC/USD")
        assertThat(candles).isEmpty()
    }


    @Test
    fun `parseCandles returns empty list for invalid JSON`() {
        val candles = TiingoResponseParser.parseCandles(sampleInvalidJsonResponse, "BTC/USD")
        assertThat(candles).isEmpty()
    }

    @Test
    fun `parseCandles handles missing fields within a candle object gracefully`() {
        val candles = TiingoResponseParser.parseCandles(sampleInvalidCandleJsonResponse, "BTC/USD")
        // Expecting 0 valid candles because the single candle element is missing required fields
        assertThat(candles).isEmpty()
    }
}
