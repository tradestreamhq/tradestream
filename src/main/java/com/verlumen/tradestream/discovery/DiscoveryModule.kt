package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.inject.AbstractModule
import com.google.inject.TypeLiteral

class DiscoveryModule : AbstractModule() {
    override fun configure() {
        bind(FitnessCalculator::class.java).to(FitnessCalculatorImpl::class.java)
        bind(GenotypeConverter::class.java).to(GenotypeConverterImpl::class.java)
        bind(ParamConfigManager::class.java).to(ParamConfigManagerImpl::class.java)
        bind(object : TypeLiteral<ImmutableList<ParamConfig>>() {}).toInstance(ParamConfigs.ALL_CONFIGS)
    }
}
