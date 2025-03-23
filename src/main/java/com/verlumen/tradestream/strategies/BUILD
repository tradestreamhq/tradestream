load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")
load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

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
        ":strategy_factories",
        ":strategy_factory",
        ":strategy_manager",
        ":strategy_manager_impl",
        ":strategy_state",
        ":strategy_state_factory_impl",
        "//third_party:guava",
        "//third_party:guice",
    ],
)

kt_jvm_library(
    name = "strategy_constants",
    srcs = ["StrategyConstants.kt"],
    deps = [
        "//protos:strategies_java_proto",
    ],
)

java_library(
    name = "strategy_engine_pipeline",
    srcs = ["StrategyEnginePipeline.java"],
    deps = [
        ":optimize_strategies",
        "//protos:marketdata_java_proto",
        "//protos:trade_signals_java_proto",
        "//src/main/java/com/verlumen/tradestream/signals:generate_trade_signals",
        "//src/main/java/com/verlumen/tradestream/signals:publish_trade_signals",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_state",
        "//third_party:beam_sdks_java_core",
        "//third_party:flogger",
        "//third_party:guice",
        "//third_party:guava",
    ],
)

java_library(
    name = "strategy_factories",
    srcs = ["StrategyFactories.java"],
    deps = [
        ":strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/movingaverages:movingaverages_lib",
        "//src/main/java/com/verlumen/tradestream/strategies/momentumoscillators:oscillators_lib",
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
        "strategy_constants",
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
        "strategy_constants",
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
