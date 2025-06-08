package com.verlumen.tradestream.postgres

import com.verlumen.tradestream.sql.BulkCopier
import com.verlumen.tradestream.sql.BulkCopierFactory
import org.postgresql.core.BaseConnection
import java.io.Reader
import java.sql.Connection

/**
 * A factory that creates [BulkCopier] instances tailored for PostgreSQL.
 */
object PostgreSQLBulkCopierFactory : BulkCopierFactory {

    /**
     * Creates a PostgreSQL-specific [BulkCopier].
     *
     * @param connection The active PostgreSQL database connection.
     * @return An instance of a [BulkCopier] that uses the PostgreSQL `COPY` command.
     */
    override fun create(connection: Connection): BulkCopier {
        return PostgresCopier(connection)
    }

    /**
     * Private implementation of the BulkCopier that holds the connection
     * and performs the copy operation.
     */
    private class PostgresCopier(private val connection: Connection) : BulkCopier {
        /**
         * Executes a bulk insert into a table using the PostgreSQL `COPY` command.
         * The data is expected to be in CSV format with a tab delimiter.
         */
        override fun copy(targetTable: String, reader: Reader) {
            val copyManager = (connection as BaseConnection).copyAPI
            val sql = "COPY $targetTable FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t')"
            copyManager.copyIn(sql, reader)
        }
    }
}
