package com.verlumen.tradestream.kafka;

import com.google.inject.Inject;
import org.apache.kafka.clients.consumer.Consumer;
import org.apache.kafka.clients.consumer.KafkaConsumer;

import java.util.Properties;

public class KafkaConsumerFactory {
    private final KafkaProperties kafkaProperties;

    @Inject
    public KafkaConsumerFactory(KafkaProperties kafkaProperties) {
        this.kafkaProperties = kafkaProperties;
    }

    public String getBootstrapServers() {
        return kafkaProperties.getBootstrapServers();
    }

    public Consumer<String, byte[]> createConsumer() {
        Properties props = new Properties();
        props.put("bootstrap.servers", kafkaProperties.getBootstrapServers());
        props.put("key.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
        props.put("value.deserializer", "org.apache.kafka.common.serialization.ByteArrayDeserializer");
        props.put("group.id", kafkaProperties.getGroupId());
        props.put("auto.offset.reset", "earliest");
        return new KafkaConsumer<>(props);
    }
} 