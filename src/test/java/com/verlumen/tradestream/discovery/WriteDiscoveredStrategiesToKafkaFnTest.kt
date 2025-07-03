package com.verlumen.tradestream.discovery

import org.apache.beam.sdk.util.SerializableUtils
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class WriteDiscoveredStrategiesToKafkaFnTest {
    @Test
    fun `kafka function should be serializable`() {
        val kafkaFn = WriteDiscoveredStrategiesToKafkaFn("localhost:9092", "test-topic")
        SerializableUtils.ensureSerializable(kafkaFn)
    }

    @Test
    fun `kafka function should be instantiable`() {
        val kafkaFn = WriteDiscoveredStrategiesToKafkaFn("localhost:9092", "test-topic")
        assert(kafkaFn.javaClass == WriteDiscoveredStrategiesToKafkaFn::class.java)
    }
}
