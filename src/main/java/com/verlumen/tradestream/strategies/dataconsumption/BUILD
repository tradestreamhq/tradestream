load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "data_consumption_lib",
    srcs = glob(["*.java"]),
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:guava",
    ],
)
