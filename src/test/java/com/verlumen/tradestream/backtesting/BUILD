load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "BacktestRunnerImplTest",
    srcs = ["BacktestRunnerImplTest.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner_impl",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:ta4j_core",
        "//third_party:truth",
    ],
)

java_test(
    name = "BacktestServiceClientImplTest",
    srcs = [
        "BacktestServiceClientImplTest.java",
    ],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:backtesting_java_grpc",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_service_client_impl",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:truth",
        "//third_party:grpc_java_api",
        "//third_party:grpc_java_inprocess",
        "//third_party:grpc_java_stub",
        "//third_party:grpc_testing",
        "//third_party:guice",
        "//third_party:guice_testlib",
    ],
    runtime_deps = [
        "//third_party:flogger_system_backend",
    ],
)

java_test(
    name = "BacktestServiceImplTest",
    srcs = ["BacktestServiceImplTest.java"],
    deps = [
        "//protos:backtesting_java_grpc",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_service_impl",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:grpc_java_api",
        "//third_party:grpc_java_stub",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
        "//third_party:truth",
    ],
    runtime_deps = [
        "//third_party:guice_testlib",
    ],
)

java_test(
    name = "GAServiceImplTest",
    size = "small",
    srcs = ["GAServiceImplTest.java"],
    deps = [
        "//protos:backtesting_java_grpc",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:ga_service_impl",
        "//src/main/java/com/verlumen/tradestream/backtesting:genetic_algorithm_orchestrator",
        "//third_party:grpc_java_api",
        "//third_party:grpc_java_stub",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:protobuf_java",
        "//third_party:truth",
    ],
)

java_test(
    name = "GeneticAlgorithmOrchestratorImplTest",
    size = "small",
    srcs = ["GeneticAlgorithmOrchestratorImplTest.java"],
    deps = [
        "//protos:backtesting_java_grpc",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_service_client",
        "//src/main/java/com/verlumen/tradestream/backtesting:genetic_algorithm_orchestrator",
        "//src/main/java/com/verlumen/tradestream/backtesting:genetic_algorithm_orchestrator_impl",
        "//src/main/java/com/verlumen/tradestream/backtesting/params:params_lib",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:jenetics",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:protobuf_java",
        "//third_party:truth",
    ],
)
