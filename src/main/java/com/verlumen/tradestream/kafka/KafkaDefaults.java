package com.verlumen.tradestream.kafka;

/**
 * KafkaDefaults holds the default configuration values for Kafka.
 */
public final class KafkaDefaults {

    // Kafka Configuration Defaults

    /** Kafka bootstrap servers */
    public static final String BOOTSTRAP_SERVERS = "localhost:9092";

    /** Kafka acknowledgment configuration */
    public static final String ACKS = "all";

    /** Number of retries */
    public static final int RETRIES = 5;

    /** Batch size in bytes */
    public static final int BATCH_SIZE = 16384;

    /** Linger time in milliseconds */
    public static final int LINGER_MS = 50;

    /** Buffer memory in bytes */
    public static final int BUFFER_MEMORY = 33554432;

    /** Key serializer class */
    public static final String KEY_SERIALIZER = "org.apache.kafka.common.serialization.StringSerializer";

    /** Value serializer class */
    public static final String VALUE_SERIALIZER = "org.apache.kafka.common.serialization.ByteArraySerializer";

    /** Protocol used to communicate with brokers (e.g., PLAINTEXT, SASL_SSL) */
    public static final String SECURITY_PROTOCOL = "PLAINTEXT";

    // Private constructor to prevent instantiation
    private KafkaDefaults() {
        throw new UnsupportedOperationException("KafkaDefaults is a utility class and cannot be instantiated.");
    }
}
