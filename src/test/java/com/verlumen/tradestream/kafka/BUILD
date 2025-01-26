load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "KafkaPropertiesTest",
    srcs = ["KafkaPropertiesTest.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_properties",
        "//third_party:truth",
    ],
)

java_test(
    name = "KafkaReadTransformImplTest",
    srcs = ["KafkaReadTransformImplTest.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_read_transform_impl",
        "//third_party:test_parameter_injector",
        "//third_party:truth",
    ],
)
