package com.verlumen.tradestream.postgres

import com.google.inject.AbstractModule
import com.verlumen.tradestream.sql.DataSource

class PostgresModule : AbstractModule() {
    override fun configure() {
        bind(DataSourceFactory::class.java).to(PostgreSQLDataSourceFactory::class.java)
    }
}
