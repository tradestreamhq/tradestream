package com.verlumen.tradestream.discovery

import com.google.common.truth.Truth.assertThat
import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.sql.BulkCopier
import com.verlumen.tradestream.sql.BulkCopierFactory
import com.verlumen.tradestream.sql.DataSourceConfig
import com.verlumen.tradestream.sql.DataSourceFactory
import com.verlumen.tradestream.strategies.SmaRsiParameters
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.ObjectInputStream
import java.io.ObjectOutputStream
import java.sql.Connection
import javax.sql.DataSource

/**
 * Unit tests to verify that all classes used in Beam pipelines are properly
 * serializable. This prevents runtime serialization errors in production.
 */
@RunWith(JUnit4::class)
class SerializationTest {

    @Test
    fun testPostgresStrategyRepositoryFactoryIsSerializable() {
        // Test that the factory can be serialized and deserialized
        val factory = PostgresStrategyRepository.Factory(
            bulkCopierFactory = MockBulkCopierFactory(),
            dataSourceFactory = MockDataSourceFactory()
        )
        
        val serialized = serialize(factory)
        val deserialized = deserialize<PostgresStrategyRepository.Factory>(serialized)
        
        assertThat(deserialized).isNotNull()
    }

    @Test
    fun testDryRunStrategyRepositoryFactoryIsSerializable() {
        val factory = DryRunStrategyRepository.Factory()
        
        val serialized = serialize(factory)
        val deserialized = deserialize<DryRunStrategyRepository.Factory>(serialized)
        
        assertThat(deserialized).isNotNull()
    }

    @Test
    fun testWriteDiscoveredStrategiesToPostgresFnIsSerializable() {
        val fn = WriteDiscoveredStrategiesToPostgresFn(
            strategyRepositoryFactory = MockStrategyRepositoryFactory(),
            dataSourceConfig = DataSourceConfig(
                serverName = "localhost",
                databaseName = "test",
                username = "test",
                password = "test",
                portNumber = 5432
            )
        )
        
        val serialized = serialize(fn)
        val deserialized = deserialize<WriteDiscoveredStrategiesToPostgresFn>(serialized)
        
        assertThat(deserialized).isNotNull()
    }

    @Test
    fun testDiscoveredStrategyIsSerializable() {
        val strategy = DiscoveredStrategy.newBuilder()
            .setSymbol("BTC/USD")
            .setScore(0.85)
            .setStrategy(
                Strategy.newBuilder()
                    .setType(StrategyType.SMA_RSI)
                    .setParameters(
                        Any.pack(
                            SmaRsiParameters.newBuilder()
                                .setMovingAveragePeriod(10)
                                .setRsiPeriod(14)
                                .setOverboughtThreshold(70.0)
                                .setOversoldThreshold(30.0)
                                .build()
                        )
                    )
                    .build()
            )
            .setStartTime(Timestamp.getDefaultInstance())
            .setEndTime(Timestamp.getDefaultInstance())
            .build()
        
        val serialized = serialize(strategy)
        val deserialized = deserialize<DiscoveredStrategy>(serialized)
        
        assertThat(deserialized).isNotNull()
        assertThat(deserialized.symbol).isEqualTo("BTC/USD")
        assertThat(deserialized.score).isEqualTo(0.85)
    }

    private fun <T> serialize(obj: T): ByteArray {
        val baos = ByteArrayOutputStream()
        ObjectOutputStream(baos).use { oos ->
            oos.writeObject(obj)
        }
        return baos.toByteArray()
    }

    @Suppress("UNCHECKED_CAST")
    private fun <T> deserialize(bytes: ByteArray): T {
        val bais = ByteArrayInputStream(bytes)
        ObjectInputStream(bais).use { ois ->
            return ois.readObject() as T
        }
    }

    // Mock classes for testing
    private class MockBulkCopierFactory : BulkCopierFactory {
        override fun create(connection: Connection): BulkCopier {
            throw UnsupportedOperationException("Mock implementation")
        }
    }

    private class MockDataSourceFactory : DataSourceFactory {
        override fun create(config: DataSourceConfig): DataSource {
            throw UnsupportedOperationException("Mock implementation")
        }
    }

    private class MockStrategyRepositoryFactory : StrategyRepository.Factory {
        override fun create(dataSourceConfig: DataSourceConfig): StrategyRepository {
            throw UnsupportedOperationException("Mock implementation")
        }
    }
} 