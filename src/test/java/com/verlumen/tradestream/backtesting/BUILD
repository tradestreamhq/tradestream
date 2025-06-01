load("@rules_java//java:defs.bzl", "java_test")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_test")

kt_jvm_test(
    name = "BacktestRequestFactoryImplTest",
    srcs = ["BacktestRequestFactoryImplTest.kt"],
    # If using Kotlin 1.6+, you might need:
    # jvm_target = "17",
    # toolchain = "@rules_kotlin//toolchains/kotlin_jvm:kt_jvm_toolchain_alias",
    test_class = "com.verlumen.tradestream.backtesting.BacktestRequestFactoryImplTest",
    deps = [
        # Library under test
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_request_factory_impl",
        # Interface (needed if the test references the interface type)
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_request_factory",
        # Protobuf dependencies
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        # Testing libraries
        "//third_party/java:junit",
        "//third_party/java:truth",
        # Other direct dependencies (if any are added to the test)
        "//third_party/java:flogger",  # Included because the Impl uses it, might be needed for test setup/verification later
        "//third_party/java:protobuf_java_util",  # For Timestamps
        "//third_party/java:guava",  # For ImmutableList if used directly in test
    ],
)

java_test(
    name = "BacktestRunnerImplTest",
    srcs = ["BacktestRunnerImplTest.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner_impl",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager",
        "//src/main/java/com/verlumen/tradestream/ta4j:ta4j_module",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "FitnessCalculatorImplTest",
    size = "small",
    srcs = ["FitnessCalculatorImplTest.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_request_factory",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_request_factory_impl",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//src/main/java/com/verlumen/tradestream/backtesting:fitness_calculator",
        "//src/main/java/com/verlumen/tradestream/backtesting:fitness_calculator_impl",
        "//src/main/java/com/verlumen/tradestream/backtesting:genotype_converter",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "GAEngineFactoryImplTest",
    srcs = ["GAEngineFactoryImplTest.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:fitness_calculator",
        "//src/main/java/com/verlumen/tradestream/backtesting:ga_engine_factory",
        "//src/main/java/com/verlumen/tradestream/backtesting:ga_engine_factory_impl",
        "//src/main/java/com/verlumen/tradestream/backtesting:param_config",
        "//src/main/java/com/verlumen/tradestream/backtesting:param_config_manager",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:truth",
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
        "//src/main/java/com/verlumen/tradestream/backtesting:ga_constants",
        "//src/main/java/com/verlumen/tradestream/backtesting:ga_engine_factory",
        "//src/main/java/com/verlumen/tradestream/backtesting:genetic_algorithm_orchestrator",
        "//src/main/java/com/verlumen/tradestream/backtesting:genetic_algorithm_orchestrator_impl",
        "//src/main/java/com/verlumen/tradestream/backtesting:genotype_converter",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "ParamConfigsTest",
    srcs = ["ParamConfigsTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:param_config",
        "//src/main/java/com/verlumen/tradestream/backtesting:param_configs",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_constants",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:test_parameter_injector",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "RunBacktestTest",
    size = "small",
    srcs = ["RunBacktestTest.java"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//src/main/java/com/verlumen/tradestream/backtesting:run_backtest",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:joda_time",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
