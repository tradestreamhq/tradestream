load("@rules_java//java:defs.bzl", "java_test")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_test")

kt_jvm_test(
    name = "DeserializeStrategyDiscoveryRequestFnTest",
    srcs = ["DeserializeStrategyDiscoveryRequestFnTest.kt"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:discovery_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:deserialize_strategy_discovery_request_fn",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
    ],
)

kt_jvm_test(
    name = "ExtractDiscoveredStrategiesFnTest",
    srcs = ["ExtractDiscoveredStrategiesFnTest.kt"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:discovery_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:extract_discovered_strategies_fn",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
    ],
)

java_test(
    name = "FitnessFunctionFactoryImplTest",
    srcs = ["FitnessFunctionFactoryImplTest.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_request_factory",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_request_factory_impl",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//src/main/java/com/verlumen/tradestream/discovery:fitness_function_factory",
        "//src/main/java/com/verlumen/tradestream/discovery:fitness_function_factory_impl",
        "//src/main/java/com/verlumen/tradestream/discovery:genotype_converter",
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
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:fitness_function_factory",
        "//src/main/java/com/verlumen/tradestream/discovery:ga_engine_factory",
        "//src/main/java/com/verlumen/tradestream/discovery:ga_engine_factory_impl",
        "//src/main/java/com/verlumen/tradestream/discovery:ga_engine_params",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
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
    name = "GenotypeConverterImplTest",
    srcs = ["GenotypeConverterImplTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/discovery:genotype_converter",
        "//src/main/java/com/verlumen/tradestream/discovery:genotype_converter_impl",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
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

kt_jvm_test(
    name = "KafkaDiscoveryRequestSourceTest",
    srcs = ["KafkaDiscoveryRequestSourceTest.kt"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//src/main/java/com/verlumen/tradestream/discovery:deserialize_strategy_discovery_request_fn",
        "//src/main/java/com/verlumen/tradestream/discovery:discovery_request_source",
        "//src/main/java/com/verlumen/tradestream/discovery:kafka_discovery_request_source",
        "//src/main/java/com/verlumen/tradestream/discovery:strategy_discovery_pipeline_options",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:guice_testlib",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:truth",
    ],
)

kt_jvm_test(
    name = "RunGADiscoveryFnTest",
    srcs = ["RunGADiscoveryFnTest.kt"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:discovery_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:ga_engine_factory",
        "//src/main/java/com/verlumen/tradestream/discovery:genotype_converter",
        "//src/main/java/com/verlumen/tradestream/discovery:run_ga_discovery_fn",
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_fetcher",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:mockito_kotlin",
        "//third_party/java:truth",
    ],
)

kt_jvm_test(
    name = "StrategyDiscoveryPipelineTest",
    srcs = ["StrategyDiscoveryPipelineTest.kt"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        # Core pipeline dependencies
        "//protos:discovery_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_request_factory",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//src/main/java/com/verlumen/tradestream/discovery:deserialize_strategy_discovery_request_fn",
        "//src/main/java/com/verlumen/tradestream/discovery:discovered_strategy_sink",
        "//src/main/java/com/verlumen/tradestream/discovery:extract_discovered_strategies_fn",
        "//src/main/java/com/verlumen/tradestream/discovery:strategy_discovery_pipeline",
        "//src/main/java/com/verlumen/tradestream/discovery:strategy_discovery_pipeline_options",
        "//src/main/java/com/verlumen/tradestream/discovery:run_ga_discovery_fn",
        "//src/main/java/com/verlumen/tradestream/discovery:write_discovered_strategies_to_postgres_fn",
        "//src/main/java/com/verlumen/tradestream/discovery:discovery_request_source",
        # Backtesting dependencies (from existing test)
        # SQL and database dependencies
        "//src/main/java/com/verlumen/tradestream/sql:data_source_factory",
        # Protobuf dependencies
        # Apache Beam dependencies
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        # Guice dependencies for dependency injection
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:guice_testlib",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:mockito_kotlin",
    ],
)

kt_jvm_test(
    name = "WriteDiscoveredStrategiesToPostgresFnTest",
    srcs = ["WriteDiscoveredStrategiesToPostgresFnTest.kt"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:discovery_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:write_discovered_strategies_to_postgres_fn",
        "//src/main/java/com/verlumen/tradestream/sql:bulk_copier_factory",
        "//src/main/java/com/verlumen/tradestream/sql:data_source_factory",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:commons_csv",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:mockito_kotlin",
        "//third_party/java:postgresql",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:truth",
    ],
)

kt_jvm_test(
    name = "StrategyDiscoveryPipelineRunnerTest",
    srcs = ["StrategyDiscoveryPipelineRunnerTest.kt"],
    runtime_deps = [
        "//third_party/java:beam_runners_flink_java",
    ],
    deps = [
        "//src/main/java/com/verlumen/tradestream/discovery:strategy_discovery_pipeline_options",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
)

kt_jvm_test(
    name = "PostgresStrategyRepositoryTest",
    srcs = ["PostgresStrategyRepositoryTest.kt"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/discovery:strategy_repository",
        "//src/main/java/com/verlumen/tradestream/sql:data_source_factory",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//third_party/java:flogger",
        "//third_party/java:guice",
        "//third_party/java:junit",
        "//third_party/java:mockito_kotlin",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
    ],
)

kt_jvm_test(
    name = "WriteDiscoveredStrategiesToKafkaFnTest",
    srcs = ["WriteDiscoveredStrategiesToKafkaFnTest.kt"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:discovery_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:write_discovered_strategies_to_kafka_fn",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
    ],
)
