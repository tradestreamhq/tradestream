"""Build rules for marketdata components."""

load("@rules_java//java:defs.bzl", "java_library", "java_test")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library", "kt_jvm_test")

package(default_visibility = ["//visibility:public"])

kt_jvm_library(
    name = "candle_fetcher",
    srcs = ["CandleFetcher.kt"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:protobuf_java",
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

# Guice module for market data components
java_library(
    name = "market_data_module",
    srcs = ["MarketDataModule.java"],
    deps = [
        ":candle_fetcher",
        ":candle_source",
        ":fill_forward_candles",
        ":fill_forward_candles_fn",
        ":influxdb_candle_fetcher",
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
