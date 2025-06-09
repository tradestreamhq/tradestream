package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.inject.AbstractModule
import com.google.inject.TypeLiteral
import com.google.inject.assistedinject.FactoryModuleBuilder

class DiscoveryModule : AbstractModule() {
    override fun configure() {
        bind(FitnessFunctionFactory::class.java).to(FitnessFunctionFactoryImpl::class.java)
        bind(GAEngineFactory::class.java).to(GAEngineFactoryImpl::class.java)
        bind(GenotypeConverter::class.java).to(GenotypeConverterImpl::class.java)
        bind(ParamConfigManager::class.java).to(ParamConfigManagerImpl::class.java)
        bind(object : TypeLiteral<ImmutableList<ParamConfig>>() {}).toInstance(ParamConfigs.ALL_CONFIGS)

        // Bind the appropriate request source implementation based on run mode
        bind(DiscoveryRequestSource::class.java).toProvider(DiscoveryRequestSourceProvider::class.java)

        // Bind the appropriate sink implementation based on run mode
        bind(DiscoveredStrategySink::class.java).toProvider(DiscoveredStrategySinkProvider::class.java)

        install(
            FactoryModuleBuilder()
                .implement(
                    WriteDiscoveredStrategiesToPostgresFn::class.java,
                    WriteDiscoveredStrategiesToPostgresFn::class.java,
                ).build(WriteDiscoveredStrategiesToPostgresFnFactory::class.java),
        )
    }
}

@Retention(AnnotationRetention.RUNTIME)
@Target(AnnotationTarget.FIELD, AnnotationTarget.VALUE_PARAMETER)
annotation class DryRun
