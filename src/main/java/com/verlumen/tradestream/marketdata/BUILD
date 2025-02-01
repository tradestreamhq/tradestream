load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
  name = "candle_author",
  srcs = ["CandleAuthor.java"],
  deps = [
    "//protos:marketdata_java_proto",
    "//third_party:beam_sdks_java_core",
    "//third_party:beam_sdks_java_extensions_protobuf",
    "//third_party:joda_time",
    "//third_party:protobuf_java_util",
  ],
)

java_library(
    name = "trade_publisher",
    srcs = ["CandlePublisher.java"],
    deps = [
        "//protos:marketdata_java_proto",
    ],
)

java_library(
    name = "trade_publisher_impl",
    srcs = ["CandlePublisherImpl.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:flogger",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:kafka_clients",
        "//third_party:protobuf_java_util",
        ":trade_publisher",
    ],
)
