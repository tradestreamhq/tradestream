package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.util.Timestamps
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

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

    private val sampleEmptyPriceDataJsonResponse = """
       [
         {
           "ticker": "btcusd",
           "baseCurrency": "btc",
           "quoteCurrency": "usd",
           "priceData": []
         }
       ]
    """.trimIndent()

    private val sampleMissingPriceDataJsonResponse = """
       [
         {
           "ticker": "btcusd",
           "baseCurrency": "btc",
           "quoteCurrency": "usd"
         }
       ]
    """.trimIndent()

    private val sampleInvalidCandleJsonResponse = """
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
               "low": 34200.25
             }
           ]
         }
       ]
    """.trimIndent()

    private val sampleEmptyArrayResponse = "[]"
    private val sampleInvalidJsonResponse = "[{\"ticker\": \"btcusd\",]" // Malformed JSON

    @Test
    fun `parseCandles parses valid response correctly`() {
        val candles = TiingoResponseParser.parseCandles(sampleJsonResponse, "BTC/USD")

        assertThat(candles).hasSize(2)

        val firstCandle = candles[0]
        assertThat(firstCandle.currencyPair).isEqualTo("BTC/USD")
        assertThat(Timestamps.toMillis(firstCandle.timestamp)).isEqualTo(1698278400000L) // 2023-10-26 00:00:00 UTC
        assertThat(firstCandle.open).isEqualTo(34500.50)
        assertThat(firstCandle.high).isEqualTo(34800.75)
        assertThat(firstCandle.low).isEqualTo(34200.25)
        assertThat(firstCandle.close).isEqualTo(34650.00)
        assertThat(firstCandle.volume).isEqualTo(1500.5)

        val secondCandle = candles[1]
        assertThat(secondCandle.currencyPair).isEqualTo("BTC/USD")
        assertThat(Timestamps.toMillis(secondCandle.timestamp)).isEqualTo(1698364800000L) // 2023-10-27 00:00:00 UTC
        assertThat(secondCandle.close).isEqualTo(34950.80)
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
    fun `parseCandles returns empty list for invalid JSON`() {
        val candles = TiingoResponseParser.parseCandles(sampleInvalidJsonResponse, "BTC/USD")
        assertThat(candles).isEmpty()
    }

    @Test
    fun `parseCandles handles missing fields within a candle object gracefully`() {
        val candles = TiingoResponseParser.parseCandles(sampleInvalidCandleJsonResponse, "BTC/USD")
        // Expecting 0 valid candles because the single candle element is missing fields
        assertThat(candles).isEmpty()
    }
}
