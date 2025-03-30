load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "candle_stream_with_defaults",
    srcs = ["CandleStreamWithDefaults.java"],
    deps = [
        ":default_trade_generator",
        ":last_candles_fn",
        ":sliding_candle_aggregator",
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:guava",
        "//third_party:joda_time",
        "//third_party:protobuf_java",
    ],
)

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

java_library(
    name = "dry_run_exchange_client_unbounded_source",
    srcs = [
        "DryRunExchangeClientUnboundedReader.java",
        "DryRunExchangeClientUnboundedSource.java",
    ],
    deps = [
        ":exchange_client_unbounded_reader",
        ":exchange_client_unbounded_source",
        ":trade_checkpoint_mark",
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:joda_time",
        "//third_party:protobuf_java_util",
    ],
)

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

java_library(
    name = "exchange_client_trade_source",
    srcs = ["ExchangeClientTradeSource.java"],
    deps = [
        ":exchange_client_unbounded_source",
        ":trade_source",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_read_transform",
        "//src/main/java/com/verlumen/tradestream/marketdata:parse_trades",
        "//third_party:beam_sdks_java_core",
        "//third_party:guice",
    ],
)

kt_jvm_library(
    name = "exchange_client_unbounded_reader",
    srcs = ["ExchangeClientUnboundedReader.kt"],
    deps = [
        ":exchange_client_unbounded_source",
        ":trade_checkpoint_mark",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:beam_sdks_java_core",
        "//third_party:guava",
    ],
)

kt_jvm_library(
    name = "exchange_client_unbounded_reader_impl",
    srcs = ["ExchangeClientUnboundedReaderImpl.kt"],
    deps = [
        ":exchange_client_unbounded_reader",
        ":exchange_client_unbounded_source",
        ":trade_checkpoint_mark",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair_supply",
        "//src/main/java/com/verlumen/tradestream/marketdata:exchange_streaming_client",
        "//third_party:beam_sdks_java_core",
        "//third_party:flogger",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:protobuf_java_util",
    ],
)

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

java_library(
    name = "exchange_streaming_client",
    srcs = ["ExchangeStreamingClient.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:guava",
    ],
)

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

java_library(
    name = "kafka_trade_source",
    srcs = ["KafkaTradeSource.java"],
    deps = [
        ":parse_trades",
        ":trade_source",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_read_transform",
        "//third_party:beam_sdks_java_core",
        "//third_party:guice",
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
    name = "market_data_module",
    srcs = ["MarketDataModule.java"],
    deps = [
        ":exchange_client_unbounded_reader",
        ":exchange_client_unbounded_reader_impl",
        ":exchange_client_unbounded_source",
        ":exchange_client_unbounded_source_impl",
        ":exchange_streaming_client",
        ":exchange_streaming_client_factory",
        ":trade_publisher",
        ":trade_publisher_impl",
        ":trade_source",
        "//protos:marketdata_java_proto",
        "//third_party:auto_value",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:protobuf_java_util",
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

java_library(
    name = "trade_source",
    srcs = ["TradeSource.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
    ],
)
