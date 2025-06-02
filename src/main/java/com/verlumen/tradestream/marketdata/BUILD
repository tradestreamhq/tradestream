"""Build rules for marketdata components."""

load("@rules_java//java:defs.bzl", "java_library", "java_test")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library", "kt_jvm_test")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "candle_combine_fn",
    srcs = ["CandleCombineFn.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:flogger",
        "//third_party/java:protobuf_java",
    ],
)

kt_jvm_library(
    name = "candle_lookback_do_fn",
    srcs = ["CandleLookbackDoFn.kt"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",  # For ProtoCoder
        "//third_party/java:flogger",
        "//third_party/java:guava",  # For ImmutableList
        "//third_party/java:joda_time",  # For Instant
    ],
)

java_library(
    name = "candle_source",
    srcs = ["CandleSource.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
    ],
)

# Coinbase specific streaming client
java_library(
    name = "coinbase_streaming_client",
    srcs = ["CoinbaseStreamingClient.java"],
    deps = [
        ":exchange_streaming_client",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party/java:flogger",
        "//third_party/java:gson",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:protobuf_java_util",
    ],
)

# Generates default/dummy trades
java_library(
    name = "default_trade_generator",
    srcs = ["DefaultTradeGenerator.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:joda_time",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
    ],
)

# Trade source for dry runs
java_library(
    name = "dry_run_trade_source",
    srcs = ["DryRunTradeSource.java"],
    deps = [
        ":trade_source",
        "//protos:marketdata_java_proto",
        "//third_party/java:auto_value",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guava",
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
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guice",
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
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:flogger",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:protobuf_java_util",
    ],
)

# Abstract base class for exchange client unbounded sources
kt_jvm_library(
    name = "exchange_client_unbounded_source",
    srcs = ["ExchangeClientUnboundedSource.kt"],
    deps = [
        ":trade_checkpoint_mark",
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
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
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:guice",
    ],
)

# Interface for exchange streaming clients
java_library(
    name = "exchange_streaming_client",
    srcs = ["ExchangeStreamingClient.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party/java:guava",
    ],
)

# Factory for creating exchange streaming clients
java_library(
    name = "exchange_streaming_client_factory",
    srcs = ["ExchangeStreamingClientFactory.java"],
    deps = [
        ":coinbase_streaming_client",
        ":exchange_streaming_client",
        "//third_party/java:guava",
        "//third_party/java:guice",
    ],
)

# Stateful DoFn for filling forward candle gaps
kt_jvm_library(
    name = "fill_forward_candles_fn",
    srcs = ["FillForwardCandlesFn.kt"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:flogger",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:joda_time",
        "//third_party/java:protobuf_java_util",
    ],
)

# PTransform wrapping the FillForwardCandlesFn
kt_jvm_library(
    name = "fill_forward_candles",
    srcs = ["FillForwardCandles.kt"],
    deps = [
        ":fill_forward_candles_fn",
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:joda_time",
    ],
)

# DoFn for buffering the last N candles
java_library(
    name = "last_candles_fn",
    srcs = ["LastCandlesFn.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:flogger",
        "//third_party/java:guava",
    ],
)

# Guice module for market data components
java_library(
    name = "market_data_module",
    srcs = ["MarketDataModule.java"],
    deps = [
        ":candle_source",
        ":dry_run_trade_source",
        ":exchange_client_trade_source",
        ":exchange_client_unbounded_source",
        ":exchange_client_unbounded_source_impl",
        ":exchange_streaming_client",
        ":exchange_streaming_client_factory",
        ":fill_forward_candles",
        ":fill_forward_candles_fn",
        ":sliding_candle_aggregator",
        ":tiingo_crypto_candle_source",
        ":tiingo_crypto_candle_transform",
        ":tiingo_crypto_fetcher_fn",
        ":trade_backed_candle_source",
        ":trade_source",
        ":trade_to_candle",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
        "//third_party/java:auto_value",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:joda_time",
        "//third_party/java:protobuf_java_util",
    ],
)

# PTransform for aggregating trades using sliding windows (contains CandleCombineFn)
java_library(
    name = "sliding_candle_aggregator",
    srcs = ["SlidingCandleAggregator.java"],
    deps = [
        ":candle_combine_fn",
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:flogger",
        "//third_party/java:joda_time",
        "//third_party/java:protobuf_java",
    ],
)

kt_jvm_library(
    name = "tiingo_crypto_candle_source",
    srcs = ["TiingoCryptoCandleSource.kt"],
    deps = [
        ":candle_source",
        ":tiingo_crypto_candle_transform",
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
    ],
)

kt_jvm_library(
    name = "tiingo_crypto_candle_transform",
    srcs = ["TiingoCryptoCandleTransform.kt"],
    visibility = ["//visibility:public"],
    deps = [
        ":tiingo_crypto_fetcher_fn",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:joda_time",
    ],
)

kt_jvm_library(
    name = "tiingo_crypto_fetcher_fn",
    srcs = ["TiingoCryptoFetcherFn.kt"],
    deps = [
        ":tiingo_response_parser",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/http:http_client",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:flogger",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:joda_time",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
    ],
)

# Tiingo Response Parser
kt_jvm_library(
    name = "tiingo_response_parser",
    srcs = ["TiingoResponseParser.kt"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:gson",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
    ],
)

java_library(
    name = "trade_backed_candle_source",
    srcs = ["TradeBackedCandleSource.java"],
    deps = [
        ":candle_source",
        ":trade_source",
        ":trade_to_candle",
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guice",
        "//third_party/java:joda_time",
        "//third_party/java:protobuf_java_util",
    ],
)

# Checkpoint mark for the unbounded source
kt_jvm_library(
    name = "trade_checkpoint_mark",
    srcs = ["TradeCheckpointMark.kt"],
    deps = [
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:joda_time",
    ],
)

# Abstract base class for trade sources
java_library(
    name = "trade_source",
    srcs = ["TradeSource.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
    ],
)

# PTransform to convert Trades to Candles (now uses ParDo with CandleCreatorFn)
kt_jvm_library(
    name = "trade_to_candle",
    srcs = ["TradeToCandle.kt"],
    deps = [
        ":candle_combine_fn",
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:flogger",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:joda_time",
        "//third_party/java:protobuf_java",
    ],
)
