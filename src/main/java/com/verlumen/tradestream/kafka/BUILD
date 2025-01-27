load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "kafka_defaults",
    srcs = ["KafkaDefaults.java"],
)

java_library(
    name = "kafka_module",
    srcs = ["KafkaModule.java"],
    deps = [
        "//third_party:auto_value",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:kafka_clients",
        ":kafka_producer_provider",
        ":kafka_properties",
    ],
)

java_library(
    name = "kafka_producer_provider",
    srcs = ["KafkaProducerProvider.java"],
    deps = [
        "//third_party:guice",
        "//third_party:kafka_clients",
        ":kafka_properties",
    ],    
)

java_library(
    name = "kafka_properties",
    srcs = ["KafkaProperties.java"],
    deps = [
        ":kafka_defaults",
    ],
)

java_library(
    name = "kafka_read_transform",
    srcs = ["KafkaReadTransform.java"],
    deps = [
        "//third_party:beam_sdks_java_core",
    ],
)

java_library(
    name = "kafka_read_transform_factory",
    srcs = ["KafkaReadTransformFactory.java"],
    deps = [
        "//third_party:guice",
        ":kafka_properties",
        ":kafka_read_transform",
        ":kafka_read_transform_impl",
    ],
)

java_library(
    name = "kafka_read_transform_impl",
    srcs = ["KafkaReadTransformImpl.java"],
    deps = [
        "//third_party:auto_value",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_io_kafka",
        "//third_party:kafka_clients",
        ":kafka_read_transform",
    ],
)
