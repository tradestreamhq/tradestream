load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "optimize_each_strategy_do_fn",
    srcs = ["OptimizeEachStrategyDoFn.java"],
    deps = [
        ":strategy_processing_request",
        ":strategy_state",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:genetic_algorithm_orchestrator",
        "//src/main/java/com/verlumen/tradestream/ta4j:bar_series_factory",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:flogger",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "optimize_strategies",
    srcs = ["OptimizeStrategies.java"],
    deps = [
        ":optimize_each_strategy_do_fn",
        ":split_by_strategy_type",
        ":strategy_processing_request",
        ":strategy_state",
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guava",
        "//third_party/java:guice",
    ],
)

java_library(
    name = "split_by_strategy_type",
    srcs = ["SplitByStrategyType.java"],
    deps = [
        ":strategy_constants",
        ":strategy_processing_request",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guava",
        "//third_party/java:guice",
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
        "//third_party/java:guava",
        "//third_party/java:guice",
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
    name = "strategy_factories",
    srcs = ["StrategyFactories.java"],
    deps = [
        ":strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/momentumoscillators:oscillators_lib",
        "//src/main/java/com/verlumen/tradestream/strategies/movingaverages:movingaverages_lib",
        "//third_party/java:guava",
    ],
)

java_library(
    name = "strategy_factory",
    srcs = ["StrategyFactory.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "strategy_manager",
    srcs = ["StrategyManager.java"],
    deps = [
        ":strategy_factory",
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "strategy_manager_impl",
    srcs = ["StrategyManagerImpl.java"],
    deps = [
        ":strategy_factory",
        ":strategy_manager",
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:mug",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)

kt_jvm_library(
    name = "strategy_processing_request",
    srcs = ["StrategyProcessingRequest.kt"],
    deps = [
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
    ],
)

java_library(
    name = "strategy_record",
    srcs = ["StrategyRecord.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "strategy_state",
    srcs = ["StrategyState.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
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
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)
