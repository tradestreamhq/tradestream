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
    name = "GeneticAlgorithmOrchestratorImplTest",
    size = "small",
    srcs = ["GeneticAlgorithmOrchestratorImplTest.java"],
    deps = [
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
        "//third_party:protobuf_java_util",
        "//third_party:truth",
    ],
)

java_test(
    name = "RunBacktestTest",
    size = "small",
    srcs = ["RunBacktestTest.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//src/main/java/com/verlumen/tradestream/backtesting:run_backtest",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_test_utils",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:joda_time",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:ta4j_core",
        "//third_party:truth",
    ],
)
