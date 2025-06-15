load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")
load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("//platforms:transition.bzl", "multi_arch")

package(default_visibility = [
    "//src/test/java/com/verlumen/tradestream/discovery:__pkg__",
])

java_binary(
    name = "app",
    main_class = "com.verlumen.tradestream.discovery.StrategyDiscoveryPipelineRunner",
    runtime_deps = [":strategy_discovery_pipeline_runner"],
)

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

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)

kt_jvm_library(
    name = "deserialize_strategy_discovery_request_fn",
    srcs = ["DeserializeStrategyDiscoveryRequestFn.kt"],
    deps = [
        "//protos:discovery_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:flogger",
        "//third_party/java:protobuf_java",
    ],
)

kt_jvm_library(
    name = "discovered_strategy_sink",
    srcs = ["DiscoveredStrategySink.kt"],
    deps = [
        "//protos:discovery_java_proto",
        "//src/main/java/com/verlumen/tradestream/sql:data_source_factory",
        "//third_party/java:beam_sdks_java_core",
    ],
)

kt_jvm_library(
    name = "discovery_module",
    srcs = ["DiscoveryModule.kt"],
    visibility = [
        "//src/main/java/com/verlumen/tradestream/pipeline:__pkg__",
    ],
    deps = [
        ":discovered_strategy_sink",
        ":discovery_request_source",
        ":dry_run_discovered_strategy_sink",
        ":dry_run_discovery_request_source",
        ":fitness_function_factory",
        ":fitness_function_factory_impl",
        ":ga_engine_factory",
        ":ga_engine_factory_impl",
        ":genotype_converter",
        ":genotype_converter_impl",
        ":kafka_discovery_request_source",
        ":param_config",
        ":param_config_manager",
        ":param_config_manager_impl",
        ":param_configs",
        ":run_ga_discovery_fn",
        ":strategy_discovery_pipeline",
        ":temporary_currency_pair_module",
        ":write_discovered_strategies_to_postgres_fn",
        "//protos:discovery_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:market_data_module",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:protobuf_java",
    ],
)

kt_jvm_library(
    name = "discovery_request_source",
    srcs = ["DiscoveryRequestSource.kt"],
    deps = [
        ":strategy_discovery_pipeline_options",
        "//protos:discovery_java_proto",
        "//third_party/java:beam_sdks_java_core",
    ],
)

kt_jvm_library(
    name = "dry_run_discovered_strategy_sink",
    srcs = ["DryRunDiscoveredStrategySink.kt"],
    deps = [
        ":discovered_strategy_sink",
        "//src/main/java/com/verlumen/tradestream/sql:data_source_factory",
        "//third_party/java:flogger",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
    ],
)

kt_jvm_library(
    name = "dry_run_discovery_request_source",
    srcs = ["DryRunDiscoveryRequestSource.kt"],
    deps = [
        ":deserialize_strategy_discovery_request_fn",
        ":discovery_request_source",
        ":strategy_discovery_pipeline_options",
        "//protos:discovery_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
    ],
)

kt_jvm_library(
    name = "extract_discovered_strategies_fn",
    srcs = ["ExtractDiscoveredStrategiesFn.kt"],
    deps = [
        "//protos:discovery_java_proto",
        "//third_party/java:beam_sdks_java_core",
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
        ":fitness_function",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
    ],
)

kt_jvm_library(
    name = "fitness_function_factory_impl",
    srcs = ["FitnessFunctionFactoryImpl.kt"],
    deps = [
        ":fitness_function",
        ":fitness_function_factory",
        ":genotype_converter",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_request_factory",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//third_party/java:guice",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "ga_constants",
    srcs = ["GAConstants.java"],
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

kt_jvm_library(
    name = "ga_engine_params",
    srcs = ["GAEngineParams.kt"],
    deps = [
        "//protos:marketdata_java_proto",  # For Candle
        "//protos:strategies_java_proto",  # For StrategyType
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

oci_image(
    name = "image",
    base = "@flink_java17",
    entrypoint = [
        "java",
        "-jar",
        "/src/main/java/com/verlumen/tradestream/discovery/app_deploy.jar",
    ],
    tars = [
        ":layer",
    ],
)

multi_arch(
    name = "images",
    image = ":image",
    platforms = [
        "//platforms:linux_arm64",
        "//platforms:linux_amd64",
    ],
)

oci_image_index(
    name = "index",
    images = [
        ":images",
    ],
)

kt_jvm_library(
    name = "kafka_discovery_request_source",
    srcs = ["KafkaDiscoveryRequestSource.kt"],
    deps = [
        ":deserialize_strategy_discovery_request_fn",
        ":discovery_request_source",
        ":strategy_discovery_pipeline_options",
        "//protos:discovery_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_io_kafka",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:kafka_clients",
    ],
)

tar(
    name = "layer",
    srcs = [":app_deploy.jar"],
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

oci_push(
    name = "push_image",
    image = ":index",
    repository = "tradestreamhq/strategy-discovery-pipeline",
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
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_fetcher",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:flogger",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java_util",
    ],
)

kt_jvm_library(
    name = "strategy_discovery_pipeline",
    srcs = [
        "StrategyDiscoveryPipeline.kt",
    ],
    deps = [
        ":discovered_strategy_sink",
        ":discovery_request_source",
        ":extract_discovered_strategies_fn",
        ":run_ga_discovery_fn",
        ":strategy_discovery_pipeline_options",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/influxdb:influx_db_config",
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_fetcher",
        "//src/main/java/com/verlumen/tradestream/sql:data_source_factory",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_io_kafka",
        "//third_party/java:flogger",
        "//third_party/java:guice",
        "//third_party/java:kafka_clients",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
    ],
)

kt_jvm_library(
    name = "strategy_discovery_pipeline_options",
    srcs = ["StrategyDiscoveryPipelineOptions.kt"],
    deps = [
        "//third_party/java:beam_sdks_java_core",
    ],
)

kt_jvm_library(
    name = "strategy_discovery_pipeline_runner",
    srcs = [
        "StrategyDiscoveryPipelineRunner.kt",
    ],
    deps = [
        ":discovery_module",
        ":strategy_discovery_pipeline",
        ":strategy_discovery_pipeline_options",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtesting_module",
        "//src/main/java/com/verlumen/tradestream/http:http_module",
        "//src/main/java/com/verlumen/tradestream/influxdb:influx_db_config",
        "//src/main/java/com/verlumen/tradestream/influxdb:influx_db_module",
        "//src/main/java/com/verlumen/tradestream/marketdata:influxdb_candle_fetcher",
        "//src/main/java/com/verlumen/tradestream/postgres:postgres_module",
        "//src/main/java/com/verlumen/tradestream/strategies:strategies_module",
        "//src/main/java/com/verlumen/tradestream/ta4j:ta4j_module",
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_io_kafka",
        "//third_party/java:guice",
    ],
)

kt_jvm_library(
    name = "temporary_currency_pair_module",
    srcs = ["TemporaryCurrencyPairModule.kt"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party/java:guava",
        "//third_party/java:guice",
    ],
)

kt_jvm_library(
    name = "write_discovered_strategies_to_postgres_fn",
    srcs = ["WriteDiscoveredStrategiesToPostgresFn.kt"],
    deps = [
        ":discovered_strategy_sink",
        "//protos:discovery_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_fetcher",
        "//src/main/java/com/verlumen/tradestream/sql:bulk_copier_factory",
        "//src/main/java/com/verlumen/tradestream/sql:data_source_factory",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:flogger",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
    ],
)
