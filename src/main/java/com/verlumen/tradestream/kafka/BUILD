load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "kafka_properties",
    srcs = ["KafkaProperties.java"],
    deps = [
        "//third_party:argparse4j",
        "//third_party:guice",
        "//third_party:mug",
    ],    
)
