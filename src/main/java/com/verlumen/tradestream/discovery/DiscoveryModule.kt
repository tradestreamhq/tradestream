package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.inject.AbstractModule
import com.google.inject.Provides
import com.google.inject.Singleton
import com.google.inject.TypeLiteral
import com.google.inject.assistedinject.FactoryModuleBuilder
import com.verlumen.tradestream.execution.RunMode
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.options.PipelineOptionsFactory

class DiscoveryModule : AbstractModule() {
    override fun configure() {
        bind(FitnessFunctionFactory::class.java).to(FitnessFunctionFactoryImpl::class.java)
        bind(GAEngineFactory::class.java).to(GAEngineFactoryImpl::class.java)
        bind(GenotypeConverter::class.java).to(GenotypeConverterImpl::class.java)
        bind(ParamConfigManager::class.java).to(ParamConfigManagerImpl::class.java)
        bind(object : TypeLiteral<ImmutableList<ParamConfig>>() {}).toInstance(ParamConfigs.ALL_CONFIGS)

        // Bind the factory
        install(
            FactoryModuleBuilder()
                .implement(StrategyDiscoveryPipeline::class.java, StrategyDiscoveryPipeline::class.java)
                .build(StrategyDiscoveryPipelineFactory::class.java),
        )

        // Bind the request source provider
        bind(DiscoveryRequestSource::class.java)
            .toProvider(DiscoveryRequestSourceProvider::class.java)
            .`in`(Singleton::class.java)

        // Bind the sink provider
        bind(DiscoveredStrategySink::class.java)
            .toProvider(DiscoveredStrategySinkProvider::class.java)
            .`in`(Singleton::class.java)

        install(
            FactoryModuleBuilder()
                .implement(
                    WriteDiscoveredStrategiesToPostgresFn::class.java,
                    WriteDiscoveredStrategiesToPostgresFn::class.java,
                ).build(WriteDiscoveredStrategiesToPostgresFnFactory::class.java),
        )
    }

    @Provides
    @Singleton
    fun providePipeline(): Pipeline = Pipeline.create(PipelineOptionsFactory.create())

    @Provides
    @Singleton
    fun provideRunMode(): RunMode {
        return RunMode.WET // Default to wet mode, can be overridden by the pipeline
    }
}

@Retention(AnnotationRetention.RUNTIME)
@Target(AnnotationTarget.FIELD, AnnotationTarget.VALUE_PARAMETER)
annotation class DryRun
