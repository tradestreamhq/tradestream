load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "data_consumption_lib",
    srcs = glob(["*.java"]),
    deps = [
        "//:autovalue",
        "//protos:marketdata_java_proto",
        "//third_party:flogger",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:kafka_clients",
    ],
)
