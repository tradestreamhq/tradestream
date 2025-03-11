load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "dry_run_kafka_read_transform",
    srcs = ["DryRunKafkaReadTransform.java"],
    deps = [
        ":kafka_read_transform",
        "//third_party:auto_value",
        "//third_party:beam_sdks_java_core",
        "//third_party:kafka_clients",
    ],
)

java_library(
    name = "kafka_defaults",
    srcs = ["KafkaDefaults.java"],
)

java_library(
    name = "kafka_module",
    srcs = ["KafkaModule.java"],
    deps = [
        ":kafka_producer_factory",
        ":kafka_producer_factory_impl",
        ":kafka_properties",
        ":kafka_read_transform",
        ":kafka_read_transform_factory",
        "//third_party:auto_value",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
    ],
)

java_library(
    name = "kafka_producer_factory",
    srcs = ["KafkaProducerProvider.java"],
    deps = [
        "//third_party:kafka_clients",
    ],    
)

java_library(
    name = "kafka_producer_factory_impl",
    srcs = ["KafkaProducerProvider.java"],
    deps = [
        ":kafka_producer_factory",
        ":kafka_properties",
        "//third_party:guice",
        "//third_party:kafka_clients",
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
        "//third_party:kafka_clients",
    ],
)

java_library(
    name = "kafka_read_transform_factory",
    srcs = ["KafkaReadTransformFactory.java"],
    deps = [
        ":dry_run_kafka_read_transform",
        ":kafka_properties",
        ":kafka_read_transform",
        ":kafka_read_transform_impl",
        "//third_party:beam_sdks_java_core",
        "//third_party:guice",
        "//third_party:kafka_clients",
    ],
)

java_library(
    name = "kafka_read_transform_impl",
    srcs = ["KafkaReadTransformImpl.java"],
    deps = [
        ":kafka_read_transform",
        "//third_party:auto_value",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_io_kafka",
        "//third_party:guava",
        "//third_party:kafka_clients",
    ],
)
