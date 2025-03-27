load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "candle_stream_with_defaults",
    srcs = ["CandleStreamWithDefaults.java"],
    deps = [
        ":sliding_candle_aggregator",
        ":default_trade_generator",
        ":last_candles_fn",
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:guava",
        "//third_party:joda_time",
        "//third_party:protobuf_java",
    ],
)

java_library(
    name = "default_trade_generator",
    srcs = ["DefaultTradeGenerator.java"],
    deps = [
      "//protos:marketdata_java_proto",
      "//third_party:beam_sdks_java_core",
      "//third_party:beam_sdks_java_extensions_protobuf",
      "//third_party:joda_time",
      "//third_party:protobuf_java",
      "//third_party:protobuf_java_util",
    ],
)

kt_jvm_library(
    name = "exchange_client_unbounded_source",
    srcs = ["WebSocketTradeUnboundedSource.kt"],
    deps = [
        ":trade_checkpoint_mark",
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
    ],
)

java_library(
  name = "last_candles_fn",
  srcs = ["LastCandlesFn.java"],
  deps = [
    "//protos:marketdata_java_proto",
    "//third_party:beam_sdks_java_core",
    "//third_party:beam_sdks_java_extensions_protobuf",
    "//third_party:flogger",
    "//third_party:guava",
  ],
)

java_library(
  name = "market_data_config",
  srcs = ["MarketDataConfig.java"],
)

java_library(
  name = "market_data_module",
  srcs = ["MarketDataModule.java"],
  deps = [
    ":market_data_config",
    ":trade_publisher",
    ":trade_publisher_impl",
    "//third_party:auto_value",
    "//third_party:guice",
    "//third_party:guice_assistedinject",
  ],
)

java_library(
    name = "multi_timeframe_candle_transform",
    srcs = ["MultiTimeframeCandleTransform.java"],
    deps = [
        ":last_candles_fn",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/time:time_frame",
        "//third_party:beam_sdks_java_core",
        "//third_party:flogger",
        "//third_party:guava",
    ],
)

java_library(
  name = "parse_trades",
  srcs = ["ParseTrades.java"],
  deps = [
    "//protos:marketdata_java_proto",
    "//third_party:beam_sdks_java_core",
    "//third_party:beam_sdks_java_extensions_protobuf",
    "//third_party:flogger",
    "//third_party:guice",
    "//third_party:protobuf_java",
  ],
)

java_library(
    name = "sliding_candle_aggregator",
    srcs = ["SlidingCandleAggregator.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:flogger",
        "//third_party:joda_time",
        "//third_party:protobuf_java",
    ],
)

kt_jvm_library(
    name = "trade_checkpoint_mark",
    srcs = ["TradeCheckpointMark.kt"],
    deps = [
        "//third_party:beam_sdks_java_core",
        "//third_party:joda_time",
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
