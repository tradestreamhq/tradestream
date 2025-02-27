load("@rules_java//java:defs.bzl", "java_binary", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "backtest_runner",
    srcs = ["BacktestRunner.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//third_party:protobuf_java",
    ],
)

java_library(
    name = "backtest_runner_impl",
    srcs = ["BacktestRunnerImpl.java"],
    deps = [
        ":backtest_runner",
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager",
        "//src/main/java/com/verlumen/tradestream/ta4j:bar_series_builder",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "backtesting_module",
    srcs = ["BacktestingModule.java"],
    deps = [
        ":backtest_runner",
        ":backtest_runner_impl",
        ":fitness_calculator",
        ":fitness_calculator_impl",
        "ga_engine_factory",
        "ga_engine_factory_impl",
        ":genetic_algorithm_orchestrator",
        ":genetic_algorithm_orchestrator_impl",
        ":genotype_converter",
        ":genotype_converter_impl",
        "//third_party:guice",
    ],
)

java_library(
    name = "fitness_calculator",
    srcs = ["FitnessCalculator.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//third_party:jenetics",
    ],
)

java_library(
    name = "fitness_calculator_impl",
    srcs = ["FitnessCalculatorImpl.java"],
    deps = [
        ":backtest_runner",
        ":fitness_calculator",
        ":genotype_converter",
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//third_party:guice",
        "//third_party:jenetics",
        "//third_party:protobuf_java",
    ],
)

java_library(
    name = "ga_constants",
    srcs = ["GAConstants.java"],
)

java_library(
    name = "ga_engine_factory",
    srcs = ["GAEngineFactory.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//third_party:jenetics",
    ],
)

java_library(
    name = "ga_engine_factory_impl",
    srcs = ["GAEngineFactoryImpl.java"],
    deps = [
        ":fitness_calculator",
        ":ga_constants",
        ":ga_engine_factory",
        "//protos:backtesting_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting/params:params_lib",
        "//third_party:guice",
        "//third_party:jenetics",
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
        ":backtest_runner",
        ":genetic_algorithm_orchestrator",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto", 
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting/params:params_lib",
        "//src/main/java/com/verlumen/tradestream/ta4j:bar_series_builder",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:jenetics",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "genotype_converter",
    srcs = ["GenotypeConverter.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party:jenetics",
        "//third_party:protobuf_java",
    ],
)

java_library(
    name = "genotype_converter_impl",
    srcs = ["GenotypeConverterImpl.java"],
    deps = [
        ":genotype_converter",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting/params:params_lib",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:jenetics",
        "//third_party:protobuf_java",
    ],
)

java_library(
    name = "run_backtest",
    srcs = ["RunBacktest.java"],
    deps = [
        ":backtest_runner",
        "//protos:backtesting_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:guice",
        "//third_party:protobuf_java",
    ],
)
