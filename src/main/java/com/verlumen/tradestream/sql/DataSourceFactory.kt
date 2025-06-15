package com.verlumen.tradestream.sql

import javax.sql.DataSource
import java.io.Serializable

/**
 * Factory interface for creating DataSource instances.
 */
interface DataSourceFactory {
    /**
     * Creates a configured DataSource instance.
     *
     * @param config Configuration parameters for the DataSource
     * @return Configured DataSource instance
     */
    fun create(config: DataSourceConfig): DataSource
}

/**
 * Configuration data class containing all parameters needed to create a DataSource.
 * Using Kotlin's data class with default parameters for clean API.
 */
data class DataSourceConfig(
    val serverName: String,
    val databaseName: String,
    val username: String,
    val password: String,
    val portNumber: Int? = null,
    val applicationName: String? = null,
    val connectTimeout: Int? = null,
    val socketTimeout: Int? = null,
    val readOnly: Boolean? = null,
) : Serializable {
    init {
        require(serverName.isNotBlank()) { "Server name cannot be blank" }
        require(databaseName.isNotBlank()) { "Database name cannot be blank" }
        require(username.isNotBlank()) { "Username cannot be blank" }
        require(password.isNotBlank()) { "Password cannot be blank" }
        portNumber?.let { require(it > 0) { "Port number must be positive" } }
        connectTimeout?.let { require(it > 0) { "Connect timeout must be positive" } }
        socketTimeout?.let { require(it > 0) { "Socket timeout must be positive" } }
    }
}
