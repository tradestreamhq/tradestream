package com.verlumen.tradestream.postgres

import com.verlumen.tradestream.sql.BulkCopier
import org.postgresql.core.BaseConnection
import java.io.StringReader
import java.sql.Connection

/**
 * A PostgreSQL implementation of [BulkCopier] that uses the native `COPY` command.
 *
 * @param connection The database connection to be used for the copy operation.
 */
class PostgreSQLBulkCopier(private val connection: Connection) : BulkCopier {

    /**
     * Executes a bulk insert into a temporary table using the `COPY` command.
     *
     * The data is expected to be in CSV format with a tab delimiter.
     */
    override fun copy(targetTable: String, reader: StringReader) {
        val copyManager = (connection as BaseConnection).copyAPI
        val sql = "COPY $targetTable FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t')"
        copyManager.copyIn(sql, reader)
    }
}
