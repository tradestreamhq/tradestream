load("@rules_java//java:defs.bzl", "java_binary", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "backtest_runner",
    srcs = ["BacktestRunner.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//third_party:auto_value",
        "//third_party:guice",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "backtest_runner_impl",
    srcs = ["BacktestRunnerImpl.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:ta4j_core",
        ":backtest_runner",
    ],
)

java_library(
    name = "backtest_service_client",
    srcs = ["BacktestServiceClient.java"],
    deps = [
        "//protos:backtesting_java_proto",
    ],
)

java_library(
    name = "backtesting_module",
    srcs = ["BacktestingModule.java"],
    deps = [
        "//third_party:guice",
    ],
)

java_library(
    name = "ga_service_client",
    srcs = ["GAServiceClient.java"],
    deps = [
        "//protos:backtesting_java_proto",
    ],
)

java_library(
    name = "genetic_algorithm_orchestrator",
    srcs = ["GeneticAlgorithmOrchestrator.java"],
    deps = [
        "//protos:backtesting_java_proto",
    ],
)

java_library(
    name = "genetic_algorithm_orchestrator_impl",
    srcs = ["GeneticAlgorithmOrchestratorImpl.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto", 
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting/params:params_lib",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:jenetics",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
        ":backtest_service_client",
        ":genetic_algorithm_orchestrator",
    ],
)
