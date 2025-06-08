package com.verlumen.tradestream.sql

import java.io.Reader
import java.sql.Connection

/**
 * An interface for an object that can perform a bulk copy operation.
 */
interface BulkCopier {
    /**
     * Copies data from a [Reader] to the specified target table.
     *
     * @param targetTable The name of the table to copy data into.
     * @param reader The [Reader] containing the data to be copied.
     */
    fun copy(targetTable: String, reader: Reader)
}

/**
 * A factory for creating [BulkCopier] instances.
 */
interface BulkCopierFactory {
    /**
     * Creates a new [BulkCopier] instance using the provided database connection.
     *
     * @param connection The database connection to be used for the copy operation.
     * @return A [BulkCopier] instance ready to perform copy operations.
     */
    fun create(connection: Connection): BulkCopier
}
