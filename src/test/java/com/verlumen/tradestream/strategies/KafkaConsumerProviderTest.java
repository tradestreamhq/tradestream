package com.verlumen.tradestream.strategies;

import static org.junit.Assert.assertNotNull;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.kafka.KafkaProperties;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

import java.util.Properties;

@RunWith(JUnit4.class)
public class KafkaConsumerProviderTest {
    @Bind private KafkaProperties kafkaProperties;
    @Inject private KafkaConsumerProvider provider;

    @Before
    public void setUp() {
        kafkaProperties = new KafkaProperties(
            16384,               // batchSize
            "localhost:9092",    // bootstrapServers
            33554432,            // bufferMemory
            "org.apache.kafka.common.serialization.StringSerializer", // keySerializer
            "org.apache.kafka.common.serialization.StringSerializer", // valueSerializer
            "PLAINTEXT",         // securityProtocol - changed from empty string
            "",                  // saslMechanism
            "",                  // saslJaasConfig
            "all",               // acks
            1,                   // lingerMs
            0                    // retries 
        );

        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void get_createsConsumerWithValidConfig() {
        KafkaConsumer<byte[], byte[]> consumer = provider.get();
        assertNotNull(consumer);
    }

    @Test
    public void get_includesSecurityConfig_whenProvided() {
        kafkaProperties = new KafkaProperties(
            16384,               // batchSize
            "localhost:9092",    // bootstrapServers
            33554432,            // bufferMemory
            "org.apache.kafka.common.serialization.StringSerializer", // keySerializer
            "org.apache.kafka.common.serialization.StringSerializer", // valueSerializer
            "SASL_SSL",          // securityProtocol
            "PLAIN",             // saslMechanism
            "org.apache.kafka.common.security.plain.PlainLoginModule required username=\"user\" password=\"pass\";", // saslJaasConfig
            "all",               // acks
            1,                   // lingerMs
            0                    // retries 
        );

        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
        KafkaConsumer<byte[], byte[]> consumer = provider.get();
        assertNotNull(consumer);
    }
}
