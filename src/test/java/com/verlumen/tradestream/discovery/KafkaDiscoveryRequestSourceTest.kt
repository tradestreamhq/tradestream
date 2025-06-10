package com.verlumen.tradestream.discovery

import com.google.common.truth.Truth.assertThat
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.BoundFieldModule
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.MockitoAnnotations
import java.io.Serializable

@RunWith(JUnit4::class)
class KafkaDiscoveryRequestSourceTest {
    
    @Inject
    lateinit var discoveryRequestSourceFactory: DiscoveryRequestSourceFactory

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        // Create Guice injector with BoundFieldModule to inject the test fixture
        val injector = Guice.createInjector(BoundFieldModule.of(this), DiscoveryModule())
        injector.injectMembers(this)
    }

    @Test
    fun testFactoryCreatesKafkaSource() {
        // Create test options
        val options = PipelineOptionsFactory.create().`as`(StrategyDiscoveryPipelineOptions::class.java).apply {
            kafkaBootstrapServers = "localhost:9092"
            strategyDiscoveryRequestTopic = "test-topic"
        }

        // Create the source using the factory
        val source = discoveryRequestSourceFactory.create(options)

        // Verify it's the correct type
        assertThat(source).isInstanceOf(KafkaDiscoveryRequestSource::class.java)
    }

    @Test 
    fun testKafkaSourceIsSerializable() {
        val options = PipelineOptionsFactory.create().`as`(StrategyDiscoveryPipelineOptions::class.java).apply {
            kafkaBootstrapServers = "localhost:9092"
            strategyDiscoveryRequestTopic = "test-topic"
        }

        val source = discoveryRequestSourceFactory.create(options)
        
        // Should be serializable for Beam
        assertThat(source).isInstanceOf(Serializable::class.java)
    }
}
