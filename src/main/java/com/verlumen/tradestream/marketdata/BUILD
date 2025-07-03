"""Build rules for marketdata components."""

load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

kt_jvm_library(
    name = "candle_fetcher",
    srcs = ["CandleFetcher.kt"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:protobuf_java",
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
kt_jvm_library(
    name = "market_data_module",
    srcs = ["MarketDataModule.kt"],
    deps = [
        ":candle_fetcher",
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
