package com.verlumen.tradestream.backtesting

import com.google.inject.AbstractModule

class BacktestingModule : AbstractModule() {
    override fun configure() {
        bind(BacktestRequestFactory::class.java).to(BacktestRequestFactoryImpl::class.java)
        bind(BacktestRunner::class.java).to(BacktestRunnerImpl::class.java)
        bind(GAEngineFactory::class.java).to(GAEngineFactoryImpl::class.java)
    }
}
