package com.verlumen.tradestream.postgres

import com.google.inject.AbstractModule
import com.verlumen.tradestream.sql.BulkCopierFactory
import com.verlumen.tradestream.sql.DataSourceFactory

class PostgresModule : AbstractModule() {
    override fun configure() {
        bind(DataSourceFactory::class.java).to(PostgreSQLDataSourceFactory::class.java)
        bind(BulkCopierFactory::class.java).toInstance(PostgreSQLBulkCopierFactory)
    }
}
