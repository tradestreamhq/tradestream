package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.MockitoAnnotations

@RunWith(JUnit4::class)
class KafkaDiscoveryRequestSourceTest {
    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    // Mock the deserialize function
    @Bind
    @Mock
    lateinit var mockDeserializeFn: DeserializeStrategyDiscoveryRequestFn

    // The class under test - will be injected by Guice
    @Inject
    lateinit var kafkaDiscoveryRequestSource: KafkaDiscoveryRequestSource

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        // Create Guice injector with BoundFieldModule and DiscoveryModule
        val injector = Guice.createInjector(
            BoundFieldModule.of(this),
            DiscoveryModule()
        )
        injector.injectMembers(this)
    }

    @Test
    fun testKafkaDiscoveryRequestSourceInjection() {
        // Verify that the Kafka discovery request source is properly injected
        assert(kafkaDiscoveryRequestSource != null) { "KafkaDiscoveryRequestSource should be injected" }
        assert(kafkaDiscoveryRequestSource is KafkaDiscoveryRequestSource) { 
            "Should inject KafkaDiscoveryRequestSource implementation" 
        }
    }

    @Test
    fun testKafkaDiscoveryRequestSourceConfiguration() {
        // Test the Kafka-specific configuration method
        val bootstrapServers = "localhost:9092"
        val topic = "test-discovery-requests"
        
        val configuredSource = kafkaDiscoveryRequestSource.withKafkaConfig(bootstrapServers, topic)
        
        assert(configuredSource != null) { "Should return configured source" }
        assert(configuredSource === kafkaDiscoveryRequestSource) { "Should return same instance for method chaining" }
    }

    @Test
    fun testKafkaDiscoveryRequestSourceIsSerializable() {
        // Verify that the Kafka implementation is serializable (important for Beam)
        // This should not throw an exception
        java.io.ObjectOutputStream(java.io.ByteArrayOutputStream()).use { oos ->
            oos.writeObject(kafkaDiscoveryRequestSource)
        }
    }

    @Test
    fun testKafkaDiscoveryRequestSourceConfigurationChaining() {
        // Test that configuration can be chained
        val result = kafkaDiscoveryRequestSource
            .withKafkaConfig("server1:9092", "topic1")
            .withKafkaConfig("server2:9092", "topic2")
        
        assert(result === kafkaDiscoveryRequestSource) { "Should support method chaining" }
    }

    @Test
    fun testKafkaDiscoveryRequestSourceExtendsAbstraction() {
        // Verify that the Kafka implementation correctly extends the abstract base class
        assert(kafkaDiscoveryRequestSource is DiscoveryRequestSource) {
            "KafkaDiscoveryRequestSource should extend DiscoveryRequestSource"
        }
    }
}
