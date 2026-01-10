package com.verlumen.tradestream.backtestingservice

import com.google.inject.AbstractModule
import com.verlumen.tradestream.backtesting.BacktestingModule

/**
 * Guice module for the Backtesting Service.
 *
 * This module wires up all dependencies required for the standalone
 * Backtesting gRPC Service.
 */
class BacktestingServiceModule : AbstractModule() {
    override fun configure() {
        // Install the core backtesting module for BacktestRunner
        install(BacktestingModule())

        // Bind the gRPC service
        bind(BacktestingGrpcService::class.java)
    }
}
