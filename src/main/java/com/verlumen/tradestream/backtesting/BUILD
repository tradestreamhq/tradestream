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

java_library(
    name = "backtest_runner",
    srcs = ["BacktestRunner.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//third_party/java:protobuf_java",
    ],
)

kt_jvm_library(
    name = "backtest_runner_impl",
    srcs = ["BacktestRunnerImpl.kt"],
    deps = [
        ":backtest_runner",
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager",
        "//src/main/java/com/verlumen/tradestream/ta4j:bar_series_factory",
        "//third_party/java:guice",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "backtesting_module",
    srcs = ["BacktestingModule.java"],
    deps = [
        "ga_engine_factory",
        "ga_engine_factory_impl",
        ":backtest_request_factory",
        ":backtest_request_factory_impl",
        ":backtest_runner",
        ":backtest_runner_impl",
        ":fitness_calculator",
        ":fitness_calculator_impl",
        ":genetic_algorithm_orchestrator",
        ":genetic_algorithm_orchestrator_impl",
        ":genotype_converter",
        ":genotype_converter_impl",
        ":param_config",
        ":param_config_manager",
        ":param_config_manager_impl",
        ":param_configs",
        "//third_party/java:guava",
        "//third_party/java:guice",
    ],
)

java_library(
    name = "chromosome_spec",
    srcs = [
        "ChromosomeSpec.java",
        "DoubleChromosomeSpec.java",
        "IntegerChromosomeSpec.java",
    ],
    deps = [
        "//third_party/java:guava",
        "//third_party/java:jenetics",
    ],
)

java_library(
    name = "fitness_calculator",
    srcs = ["FitnessCalculator.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//third_party/java:jenetics",
    ],
)

java_library(
    name = "fitness_calculator_impl",
    srcs = ["FitnessCalculatorImpl.java"],
    deps = [
        ":backtest_request_factory",
        ":backtest_runner",
        ":fitness_calculator",
        ":genotype_converter",
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//third_party/java:guice",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
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
        "//third_party/java:jenetics",
    ],
)

java_library(
    name = "ga_engine_factory_impl",
    srcs = ["GAEngineFactoryImpl.java"],
    deps = [
        ":chromosome_spec",
        ":fitness_calculator",
        ":ga_constants",
        ":ga_engine_factory",
        ":param_config",
        ":param_config_manager",
        "//protos:backtesting_java_proto",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:jenetics",
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
        ":ga_constants",
        ":ga_engine_factory",
        ":genetic_algorithm_orchestrator",
        ":genotype_converter",
        "//protos:backtesting_java_proto",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "genotype_converter",
    srcs = ["GenotypeConverter.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "genotype_converter_impl",
    srcs = ["GenotypeConverterImpl.java"],
    deps = [
        ":genotype_converter",
        ":param_config",
        ":param_config_manager",
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "param_config",
    srcs = ["ParamConfig.java"],
    deps = [
        ":chromosome_spec",
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "param_config_manager",
    srcs = ["ParamConfigManager.java"],
    deps = [
        ":param_config",
        "//protos:strategies_java_proto",
    ],
)

java_library(
    name = "param_config_manager_impl",
    srcs = ["ParamConfigManagerImpl.java"],
    deps = [
        ":param_config",
        ":param_config_manager",
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:mug",
    ],
)

java_library(
    name = "param_configs",
    srcs = [
        "ParamConfigs.java",
    ],
    deps = [
        ":param_config",
        "//src/main/java/com/verlumen/tradestream/backtesting/momentumoscillators:momentum_oscillator_params",
        "//src/main/java/com/verlumen/tradestream/backtesting/movingaverages:moving_average_params",
        "//src/main/java/com/verlumen/tradestream/backtesting/patternrecognition:pattern_recognition_params",
        "//src/main/java/com/verlumen/tradestream/backtesting/trendfollowing:trend_following_params",
        "//third_party/java:guava",
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
