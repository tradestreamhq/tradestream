load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "params_lib",
    srcs = glob(["*.java"]),
    deps = [
        "//protos:strategies_java_proto",
        "//third_party:guava",
        "//third_party:jenetics",
        "//third_party:protobuf_java",
    ],
)
