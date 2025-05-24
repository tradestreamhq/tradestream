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
        ":kafka_producer_supplier",
        ":kafka_properties",
        "//third_party/java:auto_value",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:kafka_clients",
    ],
)

java_library(
    name = "kafka_producer_supplier",
    srcs = ["KafkaProducerSupplier.java"],
    deps = [
        ":kafka_properties",
        "//third_party/java:guice",
        "//third_party/java:kafka_clients",
    ],
)

java_library(
    name = "kafka_properties",
    srcs = ["KafkaProperties.java"],
    deps = [
        ":kafka_defaults",
    ],
)
