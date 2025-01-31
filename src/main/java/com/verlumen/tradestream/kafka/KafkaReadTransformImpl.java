package com.verlumen.tradestream.kafka;

import com.google.auto.value.AutoValue;
import org.apache.beam.sdk.coders.Coder;
import org.apache.beam.sdk.io.kafka.KafkaIO;
import org.apache.beam.sdk.io.kafka.KafkaRecord;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptor;
import org.apache.kafka.common.serialization.Deserializer;

import java.util.Collections;
import java.util.Map;

@AutoValue
abstract class KafkaReadTransformImpl<K, V> extends KafkaReadTransform<K, V> {
    abstract String bootstrapServers();
    abstract String topic();
    abstract Map<String, Object> consumerConfig();
    abstract Class<? extends Deserializer<K>> keyDeserializerClass();
    abstract Class<? extends Deserializer<V>> valueDeserializerClass();
    abstract Coder<K> keyCoder(); 
    abstract Coder<V> valueCoder();

    static <K, V> Builder<K, V> builder() {
        return new AutoValue_KafkaReadTransformImpl.Builder<K, V>()
            .setConsumerConfig(Collections.emptyMap());
    }

    @AutoValue.Builder
    abstract static class Builder<K, V> {
        abstract Builder<K, V> setBootstrapServers(String bootstrapServers);
        abstract Builder<K, V> setTopic(String topic);
        abstract Builder<K, V> setConsumerConfig(Map<String, Object> consumerConfig);
        abstract Builder<K, V> setKeyDeserializerClass(
            Class<? extends Deserializer<K>> keyDeserializerClass);
        abstract Builder<K, V> setValueDeserializerClass(
            Class<? extends Deserializer<V>> valueDeserializerClass);
        abstract Builder<K, V> setKeyCoder(Coder<K> keyCoder);
        abstract Builder<K, V> setValueCoder(Coder<V> valueCoder);
        abstract KafkaReadTransformImpl<K, V> build();
    }

    @Override
    public PCollection<V> expand(PBegin input) {
        return input
            .apply("ReadFromKafka", 
                KafkaIO.<K, V>read()
                    .withBootstrapServers(bootstrapServers())
                    .withTopic(topic())
                    .withKeyDeserializerAndCoder(keyDeserializerClass(), keyCoder())
                    .withValueDeserializerAndCoder(valueDeserializerClass(), valueCoder())
                    .withConsumerConfigUpdates(consumerConfig()))
            .apply("ExtractValue",
                MapElements.into(valueCoder().getEncodedTypeDescriptor())
                    .via((KafkaRecord<K, V> record) -> record.getKV().getValue()));
    }
}
