package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.inject.AbstractModule
import com.google.inject.TypeLiteral
import com.google.inject.assistedinject.FactoryModuleBuilder

internal class BaseModule : AbstractModule() {
    override fun configure() {
        bind(FitnessFunctionFactory::class.java).to(FitnessFunctionFactoryImpl::class.java)
        bind(GAEngineFactory::class.java).to(GAEngineFactoryImpl::class.java)
        bind(GenotypeConverter::class.java).to(GenotypeConverterImpl::class.java)
        bind(ParamConfigManager::class.java).to(ParamConfigManagerImpl::class.java)
        bind(object : TypeLiteral<ImmutableList<ParamConfig>>() {}).toInstance(ParamConfigs.ALL_CONFIGS)
        install(
            FactoryModuleBuilder()
                .implement(RunGADiscoveryFn::class.java, RunGADiscoveryFn::class.java)
                .build(RunGADiscoveryFnFactory::class.java),
        )

        install(
            FactoryModuleBuilder()
                .implement(
                    WriteDiscoveredStrategiesToPostgresFn::class.java,
                    WriteDiscoveredStrategiesToPostgresFn::class.java,
                ).build(WriteDiscoveredStrategiesToPostgresFnFactory::class.java),
        )
    }

    @Provides
    fun provideCurrencyPairSupplier(): Supplier<java.util.List<CurrencyPair>> = java.util.function.Supplier { emptyList() }
}

class DryRunDiscoveryModule : AbstractModule() {
    override fun configure() {
        install(BaseModule())
        install(
            FactoryModuleBuilder()
                .implement(
                    DiscoveryRequestSource::class.java,
                    DryRunDiscoveryRequestSource::class.java,
                ).build(DiscoveryRequestSourceFactory::class.java),
        )
    }
}

class ProdDiscoveryModule : AbstractModule() {
    override fun configure() {
        install(BaseModule())
        install(
            FactoryModuleBuilder()
                .implement(
                    DiscoveryRequestSource::class.java,
                    KafkaDiscoveryRequestSource::class.java,
                ).build(DiscoveryRequestSourceFactory::class.java),
        )
    }
}
