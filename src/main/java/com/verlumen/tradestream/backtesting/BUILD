java_library(
    name = "backtest_runner",
    srcs = ["BacktestRunner.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//third_party:auto_value",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "parameterized_backtest_service_impl",
    srcs = ["ParameterizedBacktestServiceImpl.java"],
    deps = [
        "//protos:backtesting_java_grpc",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager",
        "//third_party:guice",
        "//third_party:grpc_java_api",
        "//third_party:grpc_java_stub",
        ":backtest_runner",
    ],
)
