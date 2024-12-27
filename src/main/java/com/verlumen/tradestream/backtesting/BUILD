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
    name = "backtest_service_impl",
    srcs = ["BacktestServiceImpl.java"],
    deps = [
        "//protos:backtesting_java_grpc",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager",
        "//third_party:guice",
        "//third_party:grpc_java_api",
        "//third_party:grpc_java_stub",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
        ":backtest_runner",
    ],
)

java_library(
    name = "ga_service_impl",
    srcs = ["GAServiceImpl.java"],
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
