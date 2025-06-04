load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = [
    "//src/test/java/com/verlumen/tradestream/discovery:__pkg__",
])

java_library(
    name = "chromosome_spec",
    srcs = [
        "ChromosomeSpec.java",
        "DoubleChromosomeSpec.java",
        "IntegerChromosomeSpec.java",
    ],
    visibility = [
        "//src/main/java/com/verlumen/tradestream/backtesting:__subpackages__",
        "//src/test/java/com/verlumen/tradestream/backtesting:__subpackages__",
        "//src/test/java/com/verlumen/tradestream/discovery:__pkg__",
    ],
    deps = [
        "//third_party/java:guava",
        "//third_party/java:jenetics",
    ],
)

kt_jvm_library(
    name = "discovery_module",
    srcs = ["DiscoveryModule.kt"],
    visibility = [
        "//src/main/java/com/verlumen/tradestream/pipeline:__pkg__",
    ],
    deps = [
        ":fitness_function_factory",
        ":fitness_function_factory_impl",
        ":ga_engine_factory",
        ":ga_engine_factory_impl",
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

kt_jvm_library(
    name = "fitness_function",
    srcs = ["FitnessFunction.kt"],
    deps = [
        "//third_party/java:jenetics",
    ],
)

kt_jvm_library(
    name = "fitness_function_factory",
    srcs = ["FitnessFunctionFactory.kt"],
    visibility = [
        "//src/main/java/com/verlumen/tradestream/backtesting:__pkg__",
        "//src/test/java/com/verlumen/tradestream/backtesting:__pkg__",
        "//src/test/java/com/verlumen/tradestream/discovery:__pkg__",
    ],
    deps = [
        "//protos:backtesting_java_proto",  # GAOptimizationRequest is still used by some callers, even if GAEngineFactory is decoupled
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//third_party/java:jenetics",
    ],
)

kt_jvm_library(
    name = "fitness_function_factory_impl",
    srcs = ["FitnessFunctionFactoryImpl.kt"],
    deps = [
        ":fitness_function_factory",
        ":genotype_converter",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_request_factory",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//third_party/java:guice",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "ga_constants",
    srcs = ["GAConstants.java"],
)

kt_jvm_library(
    name = "ga_engine_params",
    srcs = ["GAEngineParams.kt"],
    deps = [
        "//protos:marketdata_java_proto",  # For Candle
        "//protos:strategies_java_proto",  # For StrategyType
    ],
)

kt_jvm_library(
    name = "ga_engine_factory",
    srcs = ["GAEngineFactory.kt"],
    deps = [
        ":ga_engine_params",
        "//third_party/java:jenetics",
    ],
)

java_library(
    name = "ga_engine_factory_impl",
    srcs = ["GAEngineFactoryImpl.java"],
    deps = [
        ":chromosome_spec",
        ":fitness_function_factory",
        ":ga_constants",
        ":ga_engine_factory",
        ":ga_engine_params",
        ":param_config",
        ":param_config_manager",
        "//protos:marketdata_java_proto",  # For Candle in GAEngineParams
        "//protos:strategies_java_proto",  # For StrategyType in GAEngineParams
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:jenetics",
    ],
)

java_library(
    name = "genotype_converter",
    srcs = ["GenotypeConverter.java"],
    visibility = [
        "//src/main/java/com/verlumen/tradestream/backtesting:__pkg__",
        "//src/test/java/com/verlumen/tradestream/backtesting:__pkg__",
        "//src/test/java/com/verlumen/tradestream/discovery:__pkg__",
    ],
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
    visibility = [
        "//src/main/java/com/verlumen/tradestream/backtesting:__subpackages__",
        "//src/test/java/com/verlumen/tradestream/backtesting:__pkg__",
        "//src/test/java/com/verlumen/tradestream/discovery:__pkg__",
    ],
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
    visibility = [
        "//src/main/java/com/verlumen/tradestream/backtesting:__subpackages__",
        "//src/test/java/com/verlumen/tradestream/backtesting:__pkg__",
        "//src/test/java/com/verlumen/tradestream/discovery:__pkg__",
    ],
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

kt_jvm_library(
    name = "run_ga_discovery_fn",
    srcs = ["RunGADiscoveryFn.kt"],
    deps = [
        ":ga_engine_factory",
        ":genotype_converter",
        "//protos:backtesting_java_proto",
        "//protos:discovery_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:influxdb_candle_fetcher",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:flogger",
        "//third_party/java:guice",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java_util",
    ],
)
