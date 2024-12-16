load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "data_consumption_layer",
    srcs = glob(["DataConsumptionLayer.java"]),
    deps = [
        "@maven//:com_google_auto_value_auto_value",
        "@maven//:com_google_auto_value_auto_value_annotations",
        "@maven//:com_google_flogger_flogger",
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
        "@maven//:org_apache_kafka_kafka_clients",
        "//protos:marketdata_java_proto",
    ],
)
