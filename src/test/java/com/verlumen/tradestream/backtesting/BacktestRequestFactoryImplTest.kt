package com.verlumen.tradestream.backtesting

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.Any // Import Any
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import java.time.Instant

@RunWith(JUnit4::class)
class BacktestRequestFactoryImplTest {
    private lateinit var factory: BacktestRequestFactoryImpl
    private lateinit var sampleCandles: List<Candle>
    private lateinit var sampleStrategy: Strategy

    @Before
    fun setUp() {
        // Simple constructor, no mocks needed for instantiation
        factory = BacktestRequestFactoryImpl()

        // Create sample candle data
        val nowMillis = Instant.now().toEpochMilli()
        sampleCandles =
            listOf(
                Candle.newBuilder()
                    .setTimestamp(Timestamp.newBuilder().setSeconds(nowMillis / 1000).setNanos((nowMillis % 1000).toInt() * 1_000_000))
                    .setCurrencyPair("BTC/USD")
                    .setOpen(50000.0)
                    .setHigh(51000.0)
                    .setLow(49000.0)
                    .setClose(50500.0)
                    .setVolume(10.0)
                    .build(),
                Candle.newBuilder()
                    .setTimestamp(
                        Timestamp.newBuilder().setSeconds(
                            (nowMillis + 60000) / 1000,
                        ).setNanos(((nowMillis + 60000) % 1000).toInt() * 1_000_000),
                    )
                    .setCurrencyPair("BTC/USD")
                    .setOpen(50500.0)
                    .setHigh(51500.0)
                    .setLow(50000.0)
                    .setClose(51000.0)
                    .setVolume(12.0)
                    .build(),
            )

        // Create a sample strategy
        sampleStrategy =
            Strategy.newBuilder()
                .setType(StrategyType.SMA_RSI)
                .setParameters(Any.newBuilder().build()) // Using default/empty parameters for simplicity
                .build()
    }

    @Test
    fun create_withCandlesAndStrategy_returnsCorrectBacktestRequest() {
        // Act
        val backtestRequest = factory.create(sampleCandles, sampleStrategy)

        // Assert
        assertThat(backtestRequest).isNotNull()
        assertThat(backtestRequest.candlesList).isEqualTo(sampleCandles)
        assertThat(backtestRequest.strategy).isEqualTo(sampleStrategy)
    }

    @Test
    fun create_withEmptyCandles_returnsRequestWithEmptyCandlesList() {
        // Arrange
        val emptyCandles = emptyList<Candle>()

        // Act
        val backtestRequest = factory.create(emptyCandles, sampleStrategy)

        // Assert
        assertThat(backtestRequest).isNotNull()
        assertThat(backtestRequest.candlesList).isEmpty()
        assertThat(backtestRequest.strategy).isEqualTo(sampleStrategy)
    }
}
