package com.verlumen.tradestream.strategies;
// KafkaConsumerProvider.java

import com.google.inject.Inject;
import com.google.inject.Provider;
import com.verlumen.tradestream.kafka.KafkaProperties;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;
import org.apache.kafka.common.serialization.StringDeserializer;

import java.util.Properties;

final class KafkaConsumerProvider implements Provider<KafkaConsumer<byte[], byte[]>> {
    private static final String GROUP_ID = "strategy-engine-consumer-group";
    private static final String DEFAULT_SECURITY_PROTOCOL = "PLAINTEXT"; // Add this

    private final KafkaProperties kafkaProperties;

    @Inject
    KafkaConsumerProvider(KafkaProperties kafkaProperties) {
        this.kafkaProperties = kafkaProperties;
    }

    @Override
    public KafkaConsumer<byte[], byte[]> get() {
        Properties props = kafkaProperties.get();

        // Add consumer-specific properties
        props.put(ConsumerConfig.GROUP_ID_CONFIG, GROUP_ID);
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, ByteArrayDeserializer.class.getName());
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "latest");
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "false");
        props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, "500");
        props.put(ConsumerConfig.MAX_POLL_INTERVAL_MS_CONFIG, "300000");
        props.put(ConsumerConfig.SESSION_TIMEOUT_MS_CONFIG, "30000");
        props.put(ConsumerConfig.HEARTBEAT_INTERVAL_MS_CONFIG, "10000");

        // SASL configuration 
        String securityProtocol = kafkaProperties.securityProtocol().isEmpty() ? 
            DEFAULT_SECURITY_PROTOCOL : kafkaProperties.securityProtocol();
        props.put("security.protocol", securityProtocol);
        
        if (!kafkaProperties.saslMechanism().isEmpty()) {
            props.put("sasl.mechanism", kafkaProperties.saslMechanism());
        }
        if (!kafkaProperties.saslJaasConfig().isEmpty()) {
            props.put("sasl.jaas.config", kafkaProperties.saslJaasConfig());
        }

        return new KafkaConsumer<>(props);
    }
}
