load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "KafkaDefaultsTest",
    srcs = ["KafkaDefaultsTest.java"],
    test_class = "com.verlumen.tradestream.kafka.KafkaDefaultsTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_defaults",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "KafkaPropertiesTest",
    srcs = ["KafkaPropertiesTest.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_properties",
        "//third_party/java:truth",
    ],
)
