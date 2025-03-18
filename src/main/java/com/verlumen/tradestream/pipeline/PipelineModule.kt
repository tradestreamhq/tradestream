@file:JvmName("PipelineModuleUtility")
package com.verlumen.tradestream.pipeline

import com.google.protobuf.util.Timestamps.fromMillis
import com.google.inject.AbstractModule
import com.google.inject.Provides
import com.verlumen.tradestream.backtesting.BacktestingModule
import com.verlumen.tradestream.execution.ExecutionModule
import com.verlumen.tradestream.execution.RunMode
import com.verlumen.tradestream.kafka.DryRunKafkaReadTransform
import com.verlumen.tradestream.kafka.KafkaModule
import com.verlumen.tradestream.kafka.KafkaReadTransform
import com.verlumen.tradestream.marketdata.Trade
import com.verlumen.tradestream.signals.SignalsModule
import com.verlumen.tradestream.strategies.StrategiesModule
import com.verlumen.tradestream.ta4j.Ta4jModule
import org.apache.kafka.common.serialization.ByteArrayDeserializer
import org.apache.kafka.common.serialization.StringDeserializer

// In Java, this would be equivalent to a package-private class with static factory method
class PipelineModule private constructor(private val config: PipelineConfig) : AbstractModule() {
    private companion object {
        private val DRY_RUN_TRADE = Trade.newBuilder()
            .setExchange("FakeExhange")
            .setCurrencyPair("DRY/RUN")
            .setTradeId("trade-123")
            .setTimestamp(fromMillis(1234567))
            .setPrice(50000.0)
            .setVolume(0.1)
            .build()
    }

    override fun configure() {
        install(BacktestingModule.create())
        install(ExecutionModule.create(config.runMode()))
        install(KafkaModule.create(config.bootstrapServers()))
        install(SignalsModule.create(config.signalTopic()))
        install(StrategiesModule.create())
        install(Ta4jModule.create())
    }

    @Provides
    fun provideKafkaReadTransform(factory: KafkaReadTransform.Factory, runMode: RunMode): KafkaReadTransform<String, ByteArray> =
        if (runMode == RunMode.DRY) {
            DryRunKafkaReadTransform.builder<String, ByteArray>()
                .setBootstrapServers(config.bootstrapServers())
                .setTopic(config.tradeTopic())
                .setKeyDeserializerClass(StringDeserializer::class.java)
                .setValueDeserializerClass(ByteArrayDeserializer::class.java)
                .setDefaultValue(DRY_RUN_TRADE.toByteArray())
                .build()
        } else {
            factory.create(
                config.tradeTopic(),
                StringDeserializer::class.java,
                ByteArrayDeserializer::class.java
            )
        }

    @Provides
    fun providePipelineConfig(): PipelineConfig = config
}

// This is the Java-accessible static factory method
@JvmName("create")
fun createPipelineModule(config: PipelineConfig): PipelineModule = 
    PipelineModule::class.java.getDeclaredConstructor(PipelineConfig::class.java).apply {
        isAccessible = true 
    }.newInstance(config)
