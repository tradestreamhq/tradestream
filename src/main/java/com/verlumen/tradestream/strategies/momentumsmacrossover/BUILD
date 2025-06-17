load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "movingaverages_lib",
    srcs = glob(["*.java"]),
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//third_party/java:guava",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)
