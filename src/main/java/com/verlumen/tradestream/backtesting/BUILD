load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

kt_jvm_library(
    name = "backtest_request_factory",
    srcs = ["BacktestRequestFactory.kt"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
    ],
)

kt_jvm_library(
    name = "backtest_request_factory_impl",
    srcs = ["BacktestRequestFactoryImpl.kt"],
    deps = [
        ":backtest_request_factory",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//third_party/java:flogger",
        "//third_party/java:guice",
    ],
)

kt_jvm_library(
    name = "backtest_runner",
    srcs = ["BacktestRunner.kt"],
    deps = [
        "//protos:backtesting_java_proto",
    ],
)

kt_jvm_library(
    name = "backtest_runner_impl",
    srcs = ["BacktestRunnerImpl.kt"],
    deps = [
        ":backtest_runner",
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_specs",
        "//src/main/java/com/verlumen/tradestream/ta4j:bar_series_factory",
        "//third_party/java:guice",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)

kt_jvm_library(
    name = "remote_backtest_runner",
    srcs = ["RemoteBacktestRunner.kt"],
    deps = [
        ":backtest_runner",
        "//protos:backtesting_java_grpc",
        "//protos:backtesting_java_proto",
        "//third_party/java:flogger",
        "//third_party/java:grpc_stub",
        "//third_party/java:guice",
    ],
)

kt_jvm_library(
    name = "walk_forward_splitter",
    srcs = ["WalkForwardSplitter.kt"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
    ],
)

kt_jvm_library(
    name = "walk_forward_runner",
    srcs = ["WalkForwardRunner.kt"],
    deps = [
        ":backtest_runner",
        ":walk_forward_splitter",
        "//protos:backtesting_java_proto",
        "//third_party/java:flogger",
        "//third_party/java:guice",
    ],
)

kt_jvm_library(
    name = "strategy_validator",
    srcs = ["StrategyValidator.kt"],
    deps = [
        "//protos:backtesting_java_proto",
        "//third_party/java:flogger",
    ],
)

kt_jvm_library(
    name = "backtesting_module",
    srcs = ["BacktestingModule.kt"],
    deps = [
        ":backtest_request_factory",
        ":backtest_request_factory_impl",
        ":backtest_runner",
        ":backtest_runner_impl",
        ":strategy_validator",
        ":walk_forward_runner",
        "//third_party/java:guava",
        "//third_party/java:guice",
    ],
)

java_library(
    name = "run_backtest",
    srcs = ["RunBacktest.java"],
    deps = [
        ":backtest_runner",
        "//protos:backtesting_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guice",
        "//third_party/java:protobuf_java",
    ],
)
