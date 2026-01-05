package com.verlumen.tradestream.discovery

import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.sql.BulkCopier
import com.verlumen.tradestream.sql.BulkCopierFactory
import com.verlumen.tradestream.sql.DataSourceConfig
import com.verlumen.tradestream.sql.DataSourceFactory
import com.verlumen.tradestream.strategies.Strategy
import org.junit.Before
import org.junit.Test
import org.mockito.kotlin.doNothing
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import java.io.Reader
import java.sql.Connection
import java.sql.PreparedStatement
import javax.sql.DataSource

class PostgresStrategyRepositoryTest {
    private lateinit var repository: PostgresStrategyRepository
    private lateinit var mockBulkCopierFactory: BulkCopierFactory
    private lateinit var mockDataSourceFactory: DataSourceFactory
    private lateinit var mockDataSource: DataSource
    private lateinit var mockConnection: Connection
    private lateinit var mockPreparedStatement: PreparedStatement
    private lateinit var mockBulkCopier: BulkCopier
    private val config =
        DataSourceConfig(
            serverName = "localhost",
            databaseName = "test_db",
            username = "user",
            password = "pass",
            portNumber = 5432,
            applicationName = "test",
            connectTimeout = 10,
            socketTimeout = 10,
            readOnly = false,
        )

    @Before
    fun setUp() {
        mockBulkCopierFactory = mock()
        mockDataSourceFactory = mock()
        mockDataSource = mock()
        mockConnection = mock()
        mockPreparedStatement = mock()
        mockBulkCopier = mock()

        whenever(mockDataSourceFactory.create(config)).thenReturn(mockDataSource)
        whenever(mockDataSource.connection).thenReturn(mockConnection)
        whenever(mockConnection.prepareStatement(org.mockito.kotlin.any())).thenReturn(mockPreparedStatement)
        whenever(mockPreparedStatement.execute()).thenReturn(true)
        whenever(mockBulkCopierFactory.create(mockConnection)).thenReturn(mockBulkCopier)
        doNothing().whenever(mockBulkCopier).copy(org.mockito.kotlin.any(), org.mockito.kotlin.any<Reader>())

        repository = PostgresStrategyRepository(mockBulkCopierFactory, mockDataSourceFactory, config)
    }

    @Test
    fun testSaveAndFindAll_NoException() {
        // This test just verifies that saveAll does not throw with valid input
        val strategy =
            Strategy
                .newBuilder()
                .setStrategyName("SMA_RSI")
                .setParameters(Any.getDefaultInstance())
                .build()
        val discovered =
            DiscoveredStrategy
                .newBuilder()
                .setStrategy(strategy)
                .setScore(1.0)
                .setSymbol("BTCUSDT")
                .setStartTime(Timestamp.getDefaultInstance())
                .setEndTime(Timestamp.getDefaultInstance())
                .build()
        repository.saveAll(listOf(discovered))
        // No exception = pass
    }

    // Add more tests for findBySymbol and findAll with a real or in-memory DB if needed
}
