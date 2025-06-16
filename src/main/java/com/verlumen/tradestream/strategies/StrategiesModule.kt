package com.verlumen.tradestream.strategies

import com.google.common.collect.ImmutableList
import com.google.inject.AbstractModule
import com.google.inject.TypeLiteral

class StrategiesModule : AbstractModule() {
    override fun configure() {
        bind(object : TypeLiteral<ImmutableList<StrategyFactory<*>>>() {})
            .toInstance(ImmutableList.of())
        bind(StrategyManager::class.java).to(StrategyManagerImpl::class.java)
    }
}
