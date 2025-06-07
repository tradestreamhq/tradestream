package com.verlumen.tradestream.sql

import java.io.StringReader

/**
 * An interface for bulk copying data into a database table.
 */
interface BulkCopier {
    /**
     * Copies data from a [StringReader] to the specified target table.
     *
     * @param targetTable The name of the table to copy data into.
     * @param reader The [StringReader] containing the data to be copied, formatted as CSV with a tab delimiter.
     */
    fun copy(targetTable: String, reader: StringReader)
}
