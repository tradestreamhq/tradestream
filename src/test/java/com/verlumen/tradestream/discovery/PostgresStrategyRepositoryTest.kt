package com.verlumen.tradestream.discovery

import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import com.verlumen.tradestream.sql.BulkCopierFactory
import com.verlumen.tradestream.sql.DataSourceConfig
import com.verlumen.tradestream.sql.DataSourceFactory
import org.junit.Before
import org.junit.Test
import java.sql.Connection
import javax.sql.DataSource
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import java.sql.PreparedStatement

class PostgresStrategyRepositoryTest {
    private lateinit var repository: PostgresStrategyRepository
    private lateinit var mockBulkCopierFactory: BulkCopierFactory
    private lateinit var mockDataSourceFactory: DataSourceFactory
    private lateinit var mockDataSource: DataSource
    private lateinit var mockConnection: Connection
    private lateinit var mockPreparedStatement: PreparedStatement
    private val config = DataSourceConfig(
        serverName = "localhost",
        databaseName = "test_db",
        username = "user",
        password = "pass",
        portNumber = 5432,
        applicationName = "test",
        connectTimeout = 10,
        socketTimeout = 10,
        readOnly = false
    )

    @Before
    fun setUp() {
        mockBulkCopierFactory = mock()
        mockDataSourceFactory = mock()
        mockDataSource = mock()
        mockConnection = mock()
        mockPreparedStatement = mock()
        whenever(mockDataSourceFactory.create(config)).thenReturn(mockDataSource)
        whenever(mockDataSource.connection).thenReturn(mockConnection)
        whenever(mockConnection.prepareStatement(org.mockito.kotlin.any())).thenReturn(mockPreparedStatement)
        whenever(mockPreparedStatement.execute()).thenReturn(true)
        repository = PostgresStrategyRepository(mockBulkCopierFactory, mockDataSourceFactory, config)
    }

    @Test
    fun testSaveAndFindAll_NoException() {
        // This test just verifies that saveAll does not throw with valid input
        val strategy = Strategy.newBuilder()
            .setType(StrategyType.SMA_RSI)
            .setParameters(Any.getDefaultInstance())
            .build()
        val discovered = DiscoveredStrategy.newBuilder()
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