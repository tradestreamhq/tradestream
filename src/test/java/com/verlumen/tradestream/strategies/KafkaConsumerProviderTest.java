package com.verlumen.tradestream.strategies;

import static org.junit.Assert.assertNotNull;
import static org.mockito.Mockito.when;

import com.google.inject.Guice;
import com.google.inject.Inject;
import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.verlumen.tradestream.kafka.KafkaProperties;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnit;
import org.mockito.junit.MockitoRule;

import java.util.Properties;

@RunWith(JUnit4.class)
public class KafkaConsumerProviderTest {
    @Rule public MockitoRule mockito = MockitoJUnit.rule();

    @Mock @Bind private KafkaProperties mockKafkaProperties;
    @Inject private KafkaConsumerProvider provider;

    @Before
    public void setUp() {
        when(mockKafkaProperties.get()).thenReturn(new Properties());
        when(mockKafkaProperties.bootstrapServers()).thenReturn("localhost:9092");
        when(mockKafkaProperties.securityProtocol()).thenReturn("");
        when(mockKafkaProperties.saslMechanism()).thenReturn("");
        when(mockKafkaProperties.saslJaasConfig()).thenReturn("");

        Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
    }

    @Test
    public void get_createsConsumerWithValidConfig() {
        KafkaConsumer<byte[], byte[]> consumer = provider.get();
        assertNotNull(consumer);
    }

    @Test
    public void get_includesSecurityConfig_whenProvided() {
        when(mockKafkaProperties.securityProtocol()).thenReturn("SASL_SSL");
        when(mockKafkaProperties.saslMechanism()).thenReturn("PLAIN");
        when(mockKafkaProperties.saslJaasConfig()).thenReturn("org.apache.kafka.common.security.plain.PlainLoginModule required username=\"user\" password=\"pass\";");

        KafkaConsumer<byte[], byte[]> consumer = provider.get();
        assertNotNull(consumer);
    }
}
