package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.inject.AbstractModule
import com.google.inject.TypeLiteral

class DiscoveryModule(
    private val options: StrategyDiscoveryPipelineOptions,
) : AbstractModule() {
    override fun configure() {
        bind(StrategyDiscoveryPipelineOptions::class.java).toInstance(options)
        bind(FitnessFunctionFactory::class.java).to(FitnessFunctionFactoryImpl::class.java)
        bind(GAEngineFactory::class.java).to(GAEngineFactoryImpl::class.java)
        bind(GenotypeConverter::class.java).to(GenotypeConverterImpl::class.java)
        bind(ParamConfigManager::class.java).to(ParamConfigManagerImpl::class.java)
        bind(object : TypeLiteral<ImmutableList<ParamConfig>>() {}).toInstance(ParamConfigs.ALL_CONFIGS)
    }
}
