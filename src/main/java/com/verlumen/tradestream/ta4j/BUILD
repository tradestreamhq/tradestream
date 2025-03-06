load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
  name = "bar_series_builder",
  srcs = ["BarSeriesBuilder.java"],
  deps = [
    "//protos:marketdata_java_proto",
    "//third_party:guava",
    "//third_party:protobuf_java",
    "//third_party:protobuf_java_util",
    "//third_party:ta4j_core",
  ],
)

java_library(
  name = "bar_series_factory",
  srcs = ["BarSeriesFactory.java"],
  deps = [
    "//protos:marketdata_java_proto",
    "//third_party:guava",
    "//third_party:ta4j_core",
  ],
)
