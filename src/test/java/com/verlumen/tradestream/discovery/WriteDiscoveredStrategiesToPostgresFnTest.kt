package com.verlumen.tradestream.discovery

import com.google.common.truth.Truth.assertThat
import com.verlumen.tradestream.sql.BulkCopierFactory
import com.verlumen.tradestream.sql.DataSourceConfig
import com.verlumen.tradestream.sql.DataSourceFactory
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.ObjectInputStream
import java.io.ObjectOutputStream
import java.sql.Connection
import javax.sql.DataSource
import com.verlumen.tradestream.discovery.StrategyCsvUtil

/**
 * Unit tests for WriteDiscoveredStrategiesToPostgresFn using the new factory pattern
 * with assisted injection.
 *
 * These tests focus on the DoFn's data transformation logic using mocked dependencies.
 * Full integration tests with PostgreSQL would require a test database.
 */
@RunWith(JUnit4::class)
class WriteDiscoveredStrategiesToPostgresFnTest {

    @get:Rule
    val testPipeline: TestPipeline = TestPipeline.create()

    @Mock
    lateinit var mockDataSourceFactory: DataSourceFactory

    @Mock
    lateinit var mockBulkCopierFactory: BulkCopierFactory

    @Mock
    lateinit var mockStrategyRepositoryFactory: StrategyRepository.Factory

    @Mock
    lateinit var mockStrategyRepository: StrategyRepository

    @Mock
    lateinit var mockDataSource: DataSource

    @Mock
    lateinit var mockConnection: Connection

    private lateinit var dataSourceConfig: DataSourceConfig

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        
        dataSourceConfig = DataSourceConfig(
            serverName = "test-server",
            databaseName = "test-db",
            username = "test-user",
            password = "test-pass",
            portNumber = 5432
        )

        // Setup mock behaviors
        whenever(mockDataSourceFactory.create(any())).thenReturn(mockDataSource)
        whenever(mockDataSource.connection).thenReturn(mockConnection)
        whenever(mockStrategyRepositoryFactory.create(any())).thenReturn(mockStrategyRepository)
    }

    private class SerializableDataSourceFactory : DataSourceFactory, java.io.Serializable {
        override fun create(config: DataSourceConfig): DataSource {
            throw UnsupportedOperationException("Not needed for serialization test")
        }
    }
    private class SerializableBulkCopierFactory : BulkCopierFactory, java.io.Serializable {
        override fun create(connection: Connection): com.verlumen.tradestream.sql.BulkCopier {
            throw UnsupportedOperationException("Not needed for serialization test")
        }
    }
    private class RecordingStrategyRepository : StrategyRepository, java.io.Serializable {
        val saved = mutableListOf<DiscoveredStrategy>()
        override fun save(strategy: DiscoveredStrategy) { saved.add(strategy) }
        override fun saveAll(strategies: List<DiscoveredStrategy>) { saved.addAll(strategies) }
        override fun findBySymbol(symbol: String): List<DiscoveredStrategy> = saved.filter { it.symbol == symbol }
        override fun findAll(): List<DiscoveredStrategy> = saved
    }
    private class RecordingStrategyRepositoryFactory(val repo: RecordingStrategyRepository) : StrategyRepository.Factory, java.io.Serializable {
        override fun create(dataSourceConfig: DataSourceConfig): StrategyRepository = repo
    }

    @Test
    fun testSerialization() {
        val fn = WriteDiscoveredStrategiesToPostgresFn(
            SerializableDataSourceFactory(),
            SerializableBulkCopierFactory(),
            RecordingStrategyRepositoryFactory(RecordingStrategyRepository()),
            dataSourceConfig
        )
        val serialized = serialize(fn)
        val deserialized = deserialize<WriteDiscoveredStrategiesToPostgresFn>(serialized)
        assertThat(deserialized).isNotNull()
    }

    @Test
    fun testPipelineExecution() {
        val repo = RecordingStrategyRepository()
        val fn = WriteDiscoveredStrategiesToPostgresFn(
            SerializableDataSourceFactory(),
            SerializableBulkCopierFactory(),
            RecordingStrategyRepositoryFactory(repo),
            dataSourceConfig
        )
        val testData = listOf(
            DiscoveredStrategy.newBuilder()
                .setSymbol("BTCUSDT")
                .setStrategy(
                    Strategy.newBuilder()
                        .setType(StrategyType.SMA_RSI)
                        .build()
                )
                .setScore(0.85)
                .setStartTime(com.google.protobuf.Timestamp.getDefaultInstance())
                .setEndTime(com.google.protobuf.Timestamp.getDefaultInstance())
                .build()
        )
        val input = testPipeline.apply(Create.of(testData))
        input.apply(ParDo.of(fn))
        testPipeline.run()
        fn.finishBundle()
    }

    @Test
    fun testCsvSerialization() {
        val strategy = DiscoveredStrategy.newBuilder()
            .setSymbol("BTCUSDT")
            .setScore(0.85)
            .setStrategy(
                Strategy.newBuilder()
                    .setType(StrategyType.SMA_RSI)
                    .build()
            )
            .setStartTime(com.google.protobuf.Timestamp.getDefaultInstance())
            .setEndTime(com.google.protobuf.Timestamp.getDefaultInstance())
            .build()

        val csvRow = StrategyCsvUtil.convertToCsvRow(strategy)
        assertThat(csvRow).isNotNull()
        val csvParser = org.apache.commons.csv.CSVParser.parse(csvRow, org.apache.commons.csv.CSVFormat.TDF)
        val records = csvParser.records
        assertThat(records.size).isEqualTo(1)
        assertThat(records[0].size()).isAtLeast(5)
    }

    private fun serialize(obj: Any): ByteArray {
        return ByteArrayOutputStream().use { baos ->
            ObjectOutputStream(baos).use { oos ->
                oos.writeObject(obj)
            }
            baos.toByteArray()
        }
    }

    @Suppress("UNCHECKED_CAST")
    private inline fun <reified T> deserialize(bytes: ByteArray): T {
        return ByteArrayInputStream(bytes).use { bais ->
            ObjectInputStream(bais).use { ois ->
                ois.readObject() as T
            }
        }
    }
}
