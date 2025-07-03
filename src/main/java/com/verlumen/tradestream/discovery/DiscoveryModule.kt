package com.verlumen.tradestream.discovery

import com.google.inject.AbstractModule
import com.google.inject.assistedinject.FactoryModuleBuilder

internal class BaseModule : AbstractModule() {
    override fun configure() {
        bind(FitnessFunctionFactory::class.java).to(FitnessFunctionFactoryImpl::class.java)
        bind(GAEngineFactory::class.java).to(GAEngineFactoryImpl::class.java)
        bind(GenotypeConverter::class.java).to(GenotypeConverterImpl::class.java)

        install(
            FactoryModuleBuilder()
                .implement(RunGADiscoveryFn::class.java, RunGADiscoveryFn::class.java)
                .build(RunGADiscoveryFnFactory::class.java),
        )
    }
}

class DiscoveryModule : AbstractModule() {
    override fun configure() {
        install(BaseModule())
        install(
            FactoryModuleBuilder()
                .implement(
                    DiscoveryRequestSource::class.java,
                    KafkaDiscoveryRequestSource::class.java,
                ).build(DiscoveryRequestSourceFactory::class.java),
        )
        bind(DiscoveredStrategySinkFactory::class.java).to(DiscoveredStrategySinkFactoryImpl::class.java)
        bind(StrategyRepository.Factory::class.java).to(PostgresStrategyRepository.Factory::class.java)
    }
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
        bind(DiscoveredStrategySinkFactory::class.java).to(DiscoveredStrategySinkFactoryImpl::class.java)
        bind(StrategyRepository.Factory::class.java).to(DryRunStrategyRepository.Factory::class.java)
    }
}
