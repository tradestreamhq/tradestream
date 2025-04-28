"""Build rules for marketdata components."""

load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library", "kt_jvm_test") # Added kt_jvm_test
load("@rules_java//java:defs.bzl", "java_library", "java_test") # Added java_test

package(default_visibility = ["//visibility:public"])

# Coinbase specific streaming client
java_library(
    name = "coinbase_streaming_client",
    srcs = ["CoinbaseStreamingClient.java"],
    deps = [
        ":exchange_streaming_client",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:flogger",
        "//third_party:gson",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:protobuf_java_util",
    ],
)

# Generates default/dummy trades
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

# Trade source for dry runs
java_library(
    name = "dry_run_trade_source",
    srcs = ["DryRunTradeSource.java"],
    deps = [
        ":trade_source",
        "//protos:marketdata_java_proto",
        "//third_party:auto_value",
        "//third_party:beam_sdks_java_core",
        "//third_party:guava",
    ],
)

# Trade source using an exchange client
java_library(
    name = "exchange_client_trade_source",
    srcs = ["ExchangeClientTradeSource.java"],
    deps = [
        ":exchange_client_unbounded_source",
        ":trade_source",
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:guice",
    ],
)

# Beam UnboundedReader implementation for exchange clients
kt_jvm_library(
    name = "exchange_client_unbounded_reader",
    srcs = ["ExchangeClientUnboundedReader.kt"],
    deps = [
        ":exchange_client_unbounded_source",
        ":trade_checkpoint_mark",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//src/main/java/com/verlumen/tradestream/marketdata:exchange_streaming_client",
        "//third_party:beam_sdks_java_core",
        "//third_party:flogger",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:protobuf_java_util",
    ],
)

# Abstract base class for exchange client unbounded sources
kt_jvm_library(
    name = "exchange_client_unbounded_source",
    srcs = ["ExchangeClientUnboundedSource.kt"],
    deps = [
        ":trade_checkpoint_mark",
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
    ],
)

# Concrete implementation of the unbounded source
kt_jvm_library(
    name = "exchange_client_unbounded_source_impl",
    srcs = ["ExchangeClientUnboundedSourceImpl.kt"],
    deps = [
        ":exchange_client_unbounded_reader",
        ":exchange_client_unbounded_source",
        ":trade_checkpoint_mark",
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:guice",
    ],
)

# Interface for exchange streaming clients
java_library(
    name = "exchange_streaming_client",
    srcs = ["ExchangeStreamingClient.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:guava",
    ],
)

# Factory for creating exchange streaming clients
java_library(
    name = "exchange_streaming_client_factory",
    srcs = ["ExchangeStreamingClientFactory.java"],
    deps = [
        ":coinbase_streaming_client",
        ":exchange_streaming_client",
        "//third_party:guava",
        "//third_party:guice",
    ],
)

# DoFn for buffering the last N candles
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

# Guice module for market data components
java_library(
    name = "market_data_module",
    srcs = ["MarketDataModule.java"],
    deps = [
        ":dry_run_trade_source",
        ":exchange_client_trade_source",
        ":exchange_client_unbounded_source",
        ":exchange_client_unbounded_source_impl",
        ":exchange_streaming_client",
        ":exchange_streaming_client_factory",
        ":sliding_candle_aggregator", # Keep dependency for CandleCombineFn if needed elsewhere
        ":trade_source",
        ":trade_to_candle",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
        "//third_party:auto_value",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:protobuf_java_util",
    ],
)

# Transform for creating multi-timeframe views
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

# PTransform for aggregating trades using sliding windows (contains CandleCombineFn)
java_library(
    name = "sliding_candle_aggregator",
    srcs = ["SlidingCandleAggregator.java"],
    deps = [
        ":candle_accumulator", # Add dependency
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:flogger",
        "//third_party:joda_time",
        "//third_party:protobuf_java",
    ],
)

# Checkpoint mark for the unbounded source
kt_jvm_library(
    name = "trade_checkpoint_mark",
    srcs = ["TradeCheckpointMark.kt"],
    deps = [
        "//third_party:beam_sdks_java_core",
        "//third_party:joda_time",
    ],
)

# Abstract base class for trade sources
java_library(
    name = "trade_source",
    srcs = ["TradeSource.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
    ],
)

# PTransform to convert Trades to Candles (now uses ParDo with CandleCreatorFn)
kt_jvm_library(
    name = "trade_to_candle",
    srcs = ["TradeToCandle.kt"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:flogger",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:joda_time",
        "//third_party:protobuf_java", # Keep dependency
    ],
)
