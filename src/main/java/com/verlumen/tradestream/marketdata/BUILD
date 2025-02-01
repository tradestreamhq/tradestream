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
  name = "market_data_module",
  srcs = ["MarketDataModule.java"],
  deps = [
    ":candle_author",
    ":trade_publisher",
    ":trade_publisher_impl",
    "//third_party:guice",
  ],
)

java_library(
    name = "trade_publisher",
    srcs = ["TradePublisher.java"],
    deps = [
        "//protos:marketdata_java_proto",
    ],
)

java_library(
    name = "trade_publisher_impl",
    srcs = ["TradePublisherImpl.java"],
    deps = [
        ":trade_publisher",
        "//protos:marketdata_java_proto",
        "//third_party:flogger",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:kafka_clients",
        "//third_party:protobuf_java_util",
    ],
)
