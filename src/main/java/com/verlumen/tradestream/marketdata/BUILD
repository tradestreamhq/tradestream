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
    name = "candle_fetcher",
    srcs = ["CandleFetcher.kt"],
    deps = [
        "//protos:marketdata_java_proto",
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

kt_jvm_library(
    name = "influxdb_candle_fetcher",
    srcs = ["InfluxDbCandleFetcher.kt"],
    deps = [
        ":candle_fetcher",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/influxdb:influx_db_client_factory",
        "//src/main/java/com/verlumen/tradestream/influxdb:influx_db_config",
        "//third_party/java:flogger",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:influxdb_client_java",
        "//third_party/java:protobuf_java_util",
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
        ":candle_fetcher",
        ":candle_source",
        ":exchange_streaming_client",
        ":fill_forward_candles",
        ":fill_forward_candles_fn",
        ":influxdb_candle_fetcher",
        ":tiingo_crypto_candle_source",
        ":tiingo_crypto_candle_transform",
        ":tiingo_crypto_fetcher_fn",
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

# Checkpoint mark for the unbounded source
kt_jvm_library(
    name = "trade_checkpoint_mark",
    srcs = ["TradeCheckpointMark.kt"],
    deps = [
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:joda_time",
    ],
)
