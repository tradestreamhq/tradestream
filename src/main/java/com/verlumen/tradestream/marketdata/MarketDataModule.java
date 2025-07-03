package com.verlumen.tradestream.marketdata

import com.google.inject.AbstractModule
import com.google.inject.assistedinject.FactoryModuleBuilder

class MarketDataModule : AbstractModule() {
    override fun configure() {
        install(
            FactoryModuleBuilder()
                .implement(InfluxDbCandleFetcher::class.java, InfluxDbCandleFetcher::class.java)
                .build(InfluxDbCandleFetcher.Factory::class.java)
        )
    }
}
