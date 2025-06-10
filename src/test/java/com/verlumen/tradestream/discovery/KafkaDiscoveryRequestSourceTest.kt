package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.kafka.KafkaConsumerFactory
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.values.PCollection
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.whenever

@RunWith(JUnit4::class)
class KafkaDiscoveryRequestSourceTest {
    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    @Bind @Mock
    lateinit var kafkaConsumerFactory: KafkaConsumerFactory

    @Inject
    lateinit var kafkaSource: KafkaDiscoveryRequestSource

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        whenever(kafkaConsumerFactory.bootstrapServers).thenReturn("localhost:9092")
        whenever(kafkaConsumerFactory.createConsumer()).thenReturn(mockConsumer())

        val injector = Guice.createInjector(BoundFieldModule.of(this))
        injector.injectMembers(this)
    }

    @Test
    fun testKafkaSourceReadsRequests() {
        val input = pipeline.apply(Create.of(Unit))
        val output: PCollection<StrategyDiscoveryRequest> = input.apply(kafkaSource)

        PAssert.that(output).satisfies { requests ->
            val requestList = requests.toList()
            assert(requestList.isNotEmpty()) { "Should read at least one request" }

            // Verify request structure
            requestList.forEach { request ->
                assert(request.symbol.isNotEmpty()) { "Request should have a symbol" }
                assert(request.hasStartTime()) { "Request should have a start time" }
                assert(request.hasEndTime()) { "Request should have an end time" }
                assert(request.hasStrategyType()) { "Request should have a strategy type" }
                assert(request.hasTopN()) { "Request should have topN" }
                assert(request.hasGaConfig()) { "Request should have GA config" }
            }

            null
        }

        pipeline.run().waitUntilFinish()
    }

    private fun mockConsumer(): org.apache.kafka.clients.consumer.Consumer<String, String> {
        return object : org.apache.kafka.clients.consumer.Consumer<String, String> {
            override fun poll(timeout: Long): org.apache.kafka.clients.consumer.ConsumerRecords<String, String> {
                val request =
                    StrategyDiscoveryRequest
                        .newBuilder()
                        .setSymbol("BTC/USD")
                        .setStartTime(Timestamps.fromMillis(System.currentTimeMillis() - 100000))
                        .setEndTime(Timestamps.fromMillis(System.currentTimeMillis()))
                        .setStrategyType(StrategyType.SMA_RSI)
                        .setTopN(10)
                        .setGaConfig(
                            GAConfig
                                .newBuilder()
                                .setMaxGenerations(50)
                                .setPopulationSize(100)
                                .build(),
                        ).build()
                        .toJsonString()

                val record =
                    org.apache.kafka.clients.consumer.ConsumerRecord(
                        "strategy-discovery-requests",
                        0,
                        0L,
                        "key",
                        request,
                    )
                return org.apache.kafka.clients.consumer.ConsumerRecords(
                    mapOf(
                        org.apache.kafka.common
                            .TopicPartition("strategy-discovery-requests", 0) to listOf(record),
                    ),
                )
            }

            // Implement other required methods with empty implementations
            override fun close() {}

            override fun commitSync() {}

            override fun commitSync(timeout: Long) {}

            override fun commitSync(
                offsets: MutableMap<org.apache.kafka.common.TopicPartition, org.apache.kafka.clients.consumer.OffsetAndMetadata>,
            ) {}

            override fun commitSync(
                offsets: MutableMap<org.apache.kafka.common.TopicPartition, org.apache.kafka.clients.consumer.OffsetAndMetadata>,
                timeout: Long,
            ) {
            }

            override fun commitAsync() {}

            override fun commitAsync(callback: org.apache.kafka.clients.consumer.OffsetCommitCallback) {}

            override fun commitAsync(
                offsets: MutableMap<org.apache.kafka.common.TopicPartition, org.apache.kafka.clients.consumer.OffsetAndMetadata>,
                callback: org.apache.kafka.clients.consumer.OffsetCommitCallback,
            ) {
            }

            override fun seek(
                partition: org.apache.kafka.common.TopicPartition,
                offset: Long,
            ) {}

            override fun seekToBeginning(partitions: MutableCollection<org.apache.kafka.common.TopicPartition>) {}

            override fun seekToEnd(partitions: MutableCollection<org.apache.kafka.common.TopicPartition>) {}

            override fun position(partition: org.apache.kafka.common.TopicPartition): Long = 0

            override fun position(
                partition: org.apache.kafka.common.TopicPartition,
                timeout: Long,
            ): Long = 0

            override fun committed(
                partition: org.apache.kafka.common.TopicPartition,
            ): org.apache.kafka.clients.consumer.OffsetAndMetadata? = null

            override fun committed(
                partition: org.apache.kafka.common.TopicPartition,
                timeout: Long,
            ): org.apache.kafka.clients.consumer.OffsetAndMetadata? = null

            override fun metrics(): MutableMap<org.apache.kafka.common.MetricName, out org.apache.kafka.common.Metric> = mutableMapOf()

            override fun partitionsFor(topic: String): MutableList<org.apache.kafka.common.PartitionInfo> = mutableListOf()

            override fun partitionsFor(
                topic: String,
                timeout: Long,
            ): MutableList<org.apache.kafka.common.PartitionInfo> = mutableListOf()

            override fun listTopics(): MutableMap<String, MutableList<org.apache.kafka.common.PartitionInfo>> = mutableMapOf()

            override fun listTopics(timeout: Long): MutableMap<String, MutableList<org.apache.kafka.common.PartitionInfo>> = mutableMapOf()

            override fun paused(): MutableSet<org.apache.kafka.common.TopicPartition> = mutableSetOf()

            override fun pause(partitions: MutableCollection<org.apache.kafka.common.TopicPartition>) {}

            override fun resume(partitions: MutableCollection<org.apache.kafka.common.TopicPartition>) {}

            override fun assignment(): MutableSet<org.apache.kafka.common.TopicPartition> = mutableSetOf()

            override fun subscription(): MutableSet<String> = mutableSetOf()

            override fun unsubscribe() {}

            override fun subscribe(topics: MutableCollection<String>) {}

            override fun subscribe(pattern: java.util.regex.Pattern) {}

            override fun subscribe(
                pattern: java.util.regex.Pattern,
                callback: org.apache.kafka.clients.consumer.ConsumerRebalanceListener,
            ) {}

            override fun subscribe(
                topics: MutableCollection<String>,
                callback: org.apache.kafka.clients.consumer.ConsumerRebalanceListener,
            ) {}

            override fun wakeup() {}
        }
    }
}
