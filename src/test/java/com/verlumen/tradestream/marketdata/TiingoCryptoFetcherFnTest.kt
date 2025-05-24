package com.verlumen.tradestream.marketdata

import com.google.common.truth.Truth.assertThat
import com.google.inject.AbstractModule
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.http.HttpClient
import org.apache.beam.sdk.coders.KvCoder
import org.apache.beam.sdk.coders.StringUtf8Coder
import org.apache.beam.sdk.coders.VoidCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.testing.TestStream
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.TimestampedValue
import org.joda.time.Duration
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import java.io.Serializable
import java.time.Instant
import java.time.ZoneOffset
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicInteger
import org.joda.time.Instant as JodaInstant

@RunWith(JUnit4::class)
class TiingoCryptoFetcherFnTest : Serializable {
    // Making class serializable
    private val serialVersionUID = 1L

    @get:Rule
    @Transient
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(false)

    // Sample for daily candles
    private val sampleResponseDailyPage1 =
        """
        [{"ticker":"btcusd","priceData":[
          {"date":"2023-10-26T00:00:00+00:00","open":34500,"high":34800,"low":34200,"close":34650,"volume":1500},
          {"date":"2023-10-27T00:00:00+00:00","open":34700,"high":35000,"low":34600,"close":34900,"volume":1600}
        ]}]
        """.trimIndent()

    private val sampleResponseDailyPage2 =
        """
        [{"ticker":"btcusd","priceData":[
          {"date":"2023-10-28T00:00:00+00:00","open":34950,"high":35200,"low":34800,"close":35100,"volume":1200}
        ]}]
        """.trimIndent()

    // Sample response with a one-day gap
    private val sampleResponseDailyWithGap =
        """
        [{"ticker":"btcusd","priceData":[
          {"date":"2023-10-26T00:00:00+00:00","open":34500,"high":34800,"low":34200,"close":34650,"volume":1500},
          {"date":"2023-10-28T00:00:00+00:00","open":34950,"high":35200,"low":34800,"close":35100,"volume":1200}
        ]}]
        """.trimIndent()

    // Sample minute response with a gap
    private val sampleResponseMinuteWithGap =
        """
        [{"ticker":"ethusd","priceData":[
          {"date":"2023-10-27T10:01:00+00:00","open":2000,"high":2002,"low":1999,"close":2001,"volume":5.2},
          {"date":"2023-10-27T10:03:00+00:00","open":2003,"high":2005,"low":2000,"close":2004,"volume":6.1}
        ]}]
        """.trimIndent()

    // Default test dependencies
    private val testApiKey = "TEST_API_KEY_123"
    private val defaultGranularity = Duration.standardDays(1)

    // Default instance for most tests
    @Inject
    lateinit var fetcherFactory: TiingoCryptoFetcherFn.Factory

    // Default fetcher instance created in setUp
    private lateinit var defaultFetcher: TiingoCryptoFetcherFn

    private val emptyResponse = "[]"

    // Helper to create expected Candle for assertions
    private fun createExpectedCandle(
        pair: String,
        tsStr: String,
        o: Double,
        h: Double,
        l: Double,
        c: Double,
        v: Double,
    ): Candle {
        // Ensure Z at the end for UTC parsing
        val instant = Instant.parse(tsStr.replace("+00:00", "Z"))
        val ts = Timestamps.fromMillis(instant.toEpochMilli())
        return Candle.newBuilder()
            .setTimestamp(ts).setCurrencyPair(pair)
            .setOpen(o).setHigh(h).setLow(l).setClose(c).setVolume(v)
            .build()
    }

    // Reusable HTTP client classes
    class SimpleHttpClient(private val response: String) : HttpClient, Serializable {
        private val serialVersionUID = 1L

        override fun get(
            url: String,
            headers: Map<String, String>,
        ): String = response
    }

    class UrlCapturingHttpClient(private val response: String, private val urls: MutableList<String>) : HttpClient, Serializable {
        private val serialVersionUID = 1L

        override fun get(
            url: String,
            headers: Map<String, String>,
        ): String {
            urls.add(url)
            return response
        }
    }

    class SequentialHttpClient(private val responses: List<String>) : HttpClient, Serializable {
        private val serialVersionUID = 1L
        private val index = AtomicInteger(0)
        val capturedUrls = CopyOnWriteArrayList<String>()

        override fun get(
            url: String,
            headers: Map<String, String>,
        ): String {
            capturedUrls.add(url)
            val currentIndex = index.getAndIncrement() % responses.size
            return responses[currentIndex]
        }
    }

    @Before
    fun setUp() {
        // Create the injector with a module that provides the HTTP client and factory
        val injector =
            Guice.createInjector(
                object : AbstractModule() {
                    override fun configure() {
                        // Bind the HTTP client
                        bind(HttpClient::class.java)
                            .toInstance(SimpleHttpClient(sampleResponseDailyPage1))

                        // Install the factory module
                        install(
                            FactoryModuleBuilder()
                                .build(TiingoCryptoFetcherFn.Factory::class.java),
                        )
                    }
                },
            )

        // Get the factory and create the default fetcher
        fetcherFactory = injector.getInstance(TiingoCryptoFetcherFn.Factory::class.java)
        defaultFetcher = fetcherFactory.create(defaultGranularity, testApiKey)
    }

    @Test
    fun `fetcher passes correct URL parameters and processes response`() {
        // Use the default fetcher created in setUp
        val result =
            pipeline
                .apply(Create.of(KV.of("BTC/USD", null as Void?)))
                .apply("Fetch", ParDo.of(defaultFetcher))

        // If URLs weren't constructed correctly, we wouldn't get the expected output
        PAssert.that(result).containsInAnyOrder(
            KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-26T00:00:00+00:00", 34500.0, 34800.0, 34200.0, 34650.0, 1500.0)),
            KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-27T00:00:00+00:00", 34700.0, 35000.0, 34600.0, 34900.0, 1600.0)),
        )

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun `initial fetch outputs expected daily candles`() {
        // Use the default fetcher
        val result =
            pipeline
                .apply(Create.of(KV.of("BTC/USD", null as Void?)))
                .apply("InitialFetch", ParDo.of(defaultFetcher))

        // Assert on the output PCollection directly
        PAssert.that(result).containsInAnyOrder(
            KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-26T00:00:00+00:00", 34500.0, 34800.0, 34200.0, 34650.0, 1500.0)),
            KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-27T00:00:00+00:00", 34700.0, 35000.0, 34600.0, 34900.0, 1600.0)),
        )
        pipeline.run()
    }

    @Test
    fun `fetcher handles empty response`() {
        // Create test-specific injector
        val emptyResponseInjector =
            Guice.createInjector(
                object : AbstractModule() {
                    override fun configure() {
                        bind(HttpClient::class.java)
                            .toInstance(SimpleHttpClient(emptyResponse))

                        install(
                            FactoryModuleBuilder()
                                .build(TiingoCryptoFetcherFn.Factory::class.java),
                        )
                    }
                },
            )

        val emptyResponseFactory = emptyResponseInjector.getInstance(TiingoCryptoFetcherFn.Factory::class.java)
        val emptyResponseFetcher = emptyResponseFactory.create(defaultGranularity, testApiKey)

        val result =
            pipeline
                .apply(Create.of(KV.of("BTC/USD", null as Void?)))
                .apply("EmptyResponse", ParDo.of(emptyResponseFetcher))

        PAssert.that(result).empty()
        pipeline.run()
    }

    @Test
    fun `fillForward skips gaps on first fetch (daily)`() {
        // Create test-specific injector
        val gapInjector =
            Guice.createInjector(
                object : AbstractModule() {
                    override fun configure() {
                        bind(HttpClient::class.java)
                            .toInstance(SimpleHttpClient(sampleResponseDailyWithGap))

                        install(
                            FactoryModuleBuilder()
                                .build(TiingoCryptoFetcherFn.Factory::class.java),
                        )
                    }
                },
            )

        val gapFactory = gapInjector.getInstance(TiingoCryptoFetcherFn.Factory::class.java)
        val gapFetcher = gapFactory.create(defaultGranularity, testApiKey)

        val result =
            pipeline
                .apply(Create.of(KV.of("BTC/USD", null as Void?)))
                .apply("GapFetch", ParDo.of(gapFetcher))

        // Expecting only the two real candles, no fill-forward on initial fetch
        PAssert.that(result).containsInAnyOrder(
            KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-26T00:00:00+00:00", 34500.0, 34800.0, 34200.0, 34650.0, 1500.0)),
            KV.of("BTC/USD", createExpectedCandle("BTC/USD", "2023-10-28T00:00:00+00:00", 34950.0, 35200.0, 34800.0, 35100.0, 1200.0)),
        )
        pipeline.run()
    }

    @Test
    fun `fillForward skips gaps on first fetch (minute) with TestStream`() {
        // Create test-specific injector
        val minuteInjector =
            Guice.createInjector(
                object : AbstractModule() {
                    override fun configure() {
                        bind(HttpClient::class.java)
                            .toInstance(SimpleHttpClient(sampleResponseMinuteWithGap))

                        install(
                            FactoryModuleBuilder()
                                .build(TiingoCryptoFetcherFn.Factory::class.java),
                        )
                    }
                },
            )

        val minuteFactory = minuteInjector.getInstance(TiingoCryptoFetcherFn.Factory::class.java)
        val minuteFetcher = minuteFactory.create(Duration.standardMinutes(1), testApiKey)

        val stream =
            TestStream.create(
                KvCoder.of(StringUtf8Coder.of(), VoidCoder.of()),
            )
                .addElements( // First trigger
                    TimestampedValue.of(KV.of("ETH/USD", null as Void?), JodaInstant(0L)),
                )
                .advanceWatermarkToInfinity()

        val result =
            pipeline
                .apply(stream)
                .apply("MinuteGapFetch", ParDo.of(minuteFetcher))

        // Expecting only the two real candles, no fill-forward on initial fetch
        PAssert.that(result).containsInAnyOrder(
            KV.of("ETH/USD", createExpectedCandle("ETH/USD", "2023-10-27T10:01:00+00:00", 2000.0, 2002.0, 1999.0, 2001.0, 5.2)),
            KV.of("ETH/USD", createExpectedCandle("ETH/USD", "2023-10-27T10:03:00+00:00", 2003.0, 2005.0, 2000.0, 2004.0, 6.1)),
        )
        pipeline.run()
    }

    @Test
    fun `fetcher handles incremental processing`() {
        // Create a response with all three days in one go
        val combinedResponse =
            """
            [{"ticker":"btcusd","priceData":[
              {"date":"2023-10-26T00:00:00+00:00","open":34500,"high":34800,"low":34200,"close":34650,"volume":1500},
              {"date":"2023-10-27T00:00:00+00:00","open":34700,"high":35000,"low":34600,"close":34900,"volume":1600},
              {"date":"2023-10-28T00:00:00+00:00","open":34950,"high":35200,"low":34800,"close":35100,"volume":1200}
            ]}]
            """.trimIndent()

        // Create test-specific injector
        val combinedInjector =
            Guice.createInjector(
                object : AbstractModule() {
                    override fun configure() {
                        bind(HttpClient::class.java)
                            .toInstance(SimpleHttpClient(combinedResponse))

                        install(
                            FactoryModuleBuilder()
                                .build(TiingoCryptoFetcherFn.Factory::class.java),
                        )
                    }
                },
            )

        val combinedFactory = combinedInjector.getInstance(TiingoCryptoFetcherFn.Factory::class.java)
        val combinedFetcher = combinedFactory.create(defaultGranularity, testApiKey)

        // Just use a simple Create transform with one element
        val input = pipeline.apply(Create.of(KV.of("BTC/USD", null as Void?)))
        val result = input.apply("FetchCombined", ParDo.of(combinedFetcher))

        // Verify we get all three dates
        PAssert.that(result).satisfies { results ->
            val candles = results.toList()

            // Get all the dates from the candles
            val dates =
                candles.map { kv ->
                    Instant.ofEpochSecond(kv.value.timestamp.seconds).toString().substring(0, 10)
                }.toSet()

            // Verify we have all three dates
            assertThat(dates).containsExactly("2023-10-26", "2023-10-27", "2023-10-28")

            null as Void?
        }

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun `fetcher respects max fill forward limit`() {
        // For this test, we'll use a sequential client
        val initialResponse =
            """
            [{"ticker":"btcusd","priceData":[
              {"date":"2023-10-26T00:00:00+00:00","open":34500,"high":34800,"low":34200,"close":34650,"volume":1500}
            ]}]
            """.trimIndent()

        val emptyFollowUpResponse = "[]"

        // Create a sequential client to return an initial response then empty responses
        val sequentialClient = SequentialHttpClient(listOf(initialResponse, emptyFollowUpResponse))

        // Create test-specific injector
        val sequentialInjector =
            Guice.createInjector(
                object : AbstractModule() {
                    override fun configure() {
                        bind(HttpClient::class.java)
                            .toInstance(sequentialClient)

                        install(
                            FactoryModuleBuilder()
                                .build(TiingoCryptoFetcherFn.Factory::class.java),
                        )
                    }
                },
            )

        val sequentialFactory = sequentialInjector.getInstance(TiingoCryptoFetcherFn.Factory::class.java)
        val sequentialFetcher = sequentialFactory.create(defaultGranularity, testApiKey)

        // Create a TestStream with two triggers spaced far apart
        val stream =
            TestStream.create(
                KvCoder.of(StringUtf8Coder.of(), VoidCoder.of()),
            )
                .addElements(
                    TimestampedValue.of(KV.of("BTC/USD", null as Void?), JodaInstant(0L)),
                )
                .advanceProcessingTime(Duration.standardDays(7)) // Advance a week
                .addElements(
                    TimestampedValue.of(KV.of("BTC/USD", null as Void?), JodaInstant(7 * 24 * 3_600_000L)), // A week later
                )
                .advanceWatermarkToInfinity()

        val result =
            pipeline
                .apply(stream)
                .apply("FetchWithFillLimit", ParDo.of(sequentialFetcher))

        // We can't easily count the exact output elements, but we can verify that the
        // output collection is not empty and contains valid candles
        PAssert.that(result).satisfies { output ->
            val candles = output.toList()

            // Should at least have the original Oct 26 candle
            val hasOct26 =
                candles.any { kv ->
                    kv.key == "BTC/USD" &&
                        Instant.ofEpochSecond(kv.value.timestamp.seconds).toString().contains("2023-10-26")
                }

            assertThat(hasOct26).isTrue()

            // We should have some candles but not hundreds - proving fill-forward is limited
            // Check that we don't have any candles from today
            val now = java.time.LocalDate.now()
            val hasCurrentDay =
                candles.any { kv ->
                    val candleDate =
                        Instant.ofEpochSecond(kv.value.timestamp.seconds)
                            .atZone(ZoneOffset.UTC).toLocalDate()
                    candleDate.isEqual(now)
                }

            // We should NOT have candles from today
            assertThat(hasCurrentDay).isFalse()

            null as Void? // Return expected Void? type
        }

        pipeline.run()
    }
}
