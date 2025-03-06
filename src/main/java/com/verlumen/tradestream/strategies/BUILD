load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "candle_buffer",
    srcs = ["CandleBuffer.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:guava",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "candle_buffer_impl",
    srcs = ["CandleBufferImpl.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:guava",
        "//third_party:protobuf_java_util",
        "//third_party:ta4j_core",
        ":candle_buffer",
    ],
)

java_library(
    name = "optimize_strategies",
    srcs = ["OptimizeStrategies.java"],
    deps = [
        ":strategy_state",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:genetic_algorithm_orchestrator",
        "//src/main/java/com/verlumen/tradestream/ta4j:bar_series_factory",
        "//third_party:beam_sdks_java_core",
        "//third_party:flogger",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "strategies_module",
    srcs = ["StrategiesModule.java"],
    deps = [
        ":candle_buffer",
        ":candle_buffer_impl",
        ":strategy_factories",
        ":strategy_factory",
        ":strategy_manager",
        ":strategy_manager_impl",
        ":strategy_state",
        ":strategy_state_factory_impl",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtesting_module",
        "//src/main/java/com/verlumen/tradestream/signals:signals_module",
        "//src/main/java/com/verlumen/tradestream/signals:trade_signal_publisher",
        "//third_party:auto_value",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:kafka_clients",
    ],
)

java_library(
    name = "strategy_factories",
    srcs = ["StrategyFactories.java"],
    deps = [
        ":strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/movingaverages:movingaverages_lib",
        "//src/main/java/com/verlumen/tradestream/strategies/oscillators:oscillators_lib",
        "//third_party:guava",
    ],
)

java_library(
    name = "strategy_factory",
    srcs = ["StrategyFactory.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "strategy_manager",
    srcs = ["StrategyManager.java"],
    deps = [
        ":strategy_factory",
        "//protos:strategies_java_proto",
        "//third_party:guava",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "strategy_manager_impl",
    srcs = ["StrategyManagerImpl.java"],
    deps = [
        ":strategy_factory",
        ":strategy_manager",
        "//protos:strategies_java_proto",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:mug",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "strategy_record",
    srcs = ["StrategyRecord.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party:guava",
        "//third_party:protobuf_java",
    ],
)

java_library(
    name = "strategy_state",
    srcs = ["StrategyState.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "strategy_state_factory_impl",
    srcs = ["StrategyStateFactoryImpl.java"],
    deps = [
        ":strategy_manager",
        ":strategy_record",
        ":strategy_state",
        "//protos:strategies_java_proto",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
    ],
)
