package com.verlumen.tradestream.postgres

import org.postgresql.ds.PGSimpleDataSource
import java.sql.Connection
import javax.sql.DataSource

/**
 * PostgreSQL implementation of DataSourceFactory using PGSimpleDataSource
 * as recommended by the PostgreSQL JDBC documentation.
 */
class PostgreSQLDataSourceFactory : DataSourceFactory {
    override fun create(config: DataSourceConfig): DataSource {
        // Create and configure PGSimpleDataSource as recommended
        val ds =
            PGSimpleDataSource().apply {
                // Required connection parameters
                serverName = config.serverName
                databaseName = config.databaseName
                user = config.username
                password = config.password

                // Optional parameters with null checks
                config.portNumber?.let { portNumber = it }
                config.applicationName?.let { applicationName = it }
                config.connectTimeout?.let { connectTimeout = it }
                config.socketTimeout?.let { socketTimeout = it }
                config.readOnly?.let { isReadOnly = it }
            }

        // Upcast to DataSource interface to insulate code from implementation
        return ds
    }
}

// Extension function for convenient DataSource usage with automatic resource management
fun <T> DataSource.useConnection(block: (Connection) -> T): T = connection.use(block)
