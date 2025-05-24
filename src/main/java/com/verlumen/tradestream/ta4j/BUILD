load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "bar_series_builder",
    srcs = ["BarSeriesBuilder.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:guava",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "bar_series_factory",
    srcs = ["BarSeriesFactory.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:guava",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "ta4j_module",
    srcs = ["Ta4jModule.java"],
    deps = [
        ":bar_series_builder",
        ":bar_series_factory",
        "//third_party/java:guice",
    ],
)
