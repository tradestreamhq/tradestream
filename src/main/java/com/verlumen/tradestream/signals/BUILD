load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "generate_trade_signals",
    srcs = ["GenerateTradeSignals.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//protos:trade_signals_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_state",
        "//src/main/java/com/verlumen/tradestream/ta4j:bar_series_factory",
        "//third_party:beam_sdks_java_core",
        "//third_party:flogger",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "publish_trade_signals",
    srcs = ["PublishTradeSignals.java"],
    deps = [
        ":trade_signal_publisher",
        "//protos:trade_signals_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:flogger",
        "//third_party:guice",
    ],
)

java_library(
    name = "signals_module",
    srcs = ["SignalsModule.java"],
    deps = [
        ":trade_signal_publisher",
        ":trade_signal_publisher_impl",
        "//third_party:auto_value",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
    ],
)

java_library(
    name = "trade_signal_publisher",
    srcs = ["TradeSignalPublisher.java"],
    deps = [
        "//protos:trade_signals_java_proto",
    ],
)

java_library(
    name = "trade_signal_publisher_impl",
    srcs = ["TradeSignalPublisherImpl.java"],
    deps = [
        ":trade_signal_publisher",
        "//protos:trade_signals_java_proto",
        "//third_party:flogger",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:kafka_clients",
        "//third_party:protobuf_java_util",
    ],
)
