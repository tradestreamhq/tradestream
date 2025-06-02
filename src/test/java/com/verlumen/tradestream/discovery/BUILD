load("@rules_java//java:defs.bzl", "java_test")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_test")

package(default_visibility = ["//visibility:public"])

kt_jvm_test(
    name = "DeserializeStrategyDiscoveryRequestFnTest",
    srcs = ["DeserializeStrategyDiscoveryRequestFnTest.kt"],
    test_class = "com.verlumen.tradestream.discovery.DeserializeStrategyDiscoveryRequestFnTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/discovery:strategy_discovery_pipeline_lib",
        "//protos:discovery_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:strategy_discovery_pipeline_lib",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:junit",
        "//third_party/java:truth",
        "//third_party/kotlin:kotlin_stdlib",
    ],
)

kt_jvm_test(
    name = "RunGADiscoveryFnTest",
    srcs = ["RunGADiscoveryFnTest.kt"],
    test_class = "com.verlumen.tradestream.discovery.RunGADiscoveryFnTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/discovery:strategy_discovery_pipeline_lib",
        "//protos:discovery_java_proto",
        "//protos:strategies_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:backtesting_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:ga_engine_factory",
        "//src/main/java/com/verlumen/tradestream/backtesting:genotype_converter",
        "//src/main/java/com/verlumen/tradestream/backtesting:fitness_calculator",
        "//src/main/java/com/verlumen/tradestream/marketdata:influxdb_candle_fetcher",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:truth",
        "//third_party/java:mockito_core",
        "//third_party/java:mockito_kotlin",
    ],
)

kt_jvm_test(
    name = "ExtractDiscoveredStrategiesFnTest",
    srcs = ["ExtractDiscoveredStrategiesFnTest.kt"],
    test_class = "com.verlumen.tradestream.discovery.ExtractDiscoveredStrategiesFnTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/discovery:strategy_discovery_pipeline_lib",
        "//protos:discovery_java_proto",
        "//protos:strategies_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:junit",
        "//third_party/java:truth",
        "//third_party/java:protobuf_java_util",
    ],
)

kt_jvm_test(
    name = "DiscoveredStrategyToStrategiesStatementSetterTest",
    srcs = ["DiscoveredStrategyToStrategiesStatementSetterTest.kt"],
    test_class = "com.verlumen.tradestream.discovery.DiscoveredStrategyToStrategiesStatementSetterTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/discovery:strategy_discovery_pipeline_lib",
        "//protos:discovery_java_proto",
        "//protos:strategies_java_proto",
        "//third_party/java:junit",
        "//third_party/java:truth",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java_util",

java_test(
    name = "GenotypeConverterImplTest",
    size = "small",
    srcs = ["GenotypeConverterImplTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/discovery:genotype_converter",
        "//src/main/java/com/verlumen/tradestream/discovery:genotype_converter_impl",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config_manager",
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
    name = "ParamConfigsTest",
    srcs = ["ParamConfigsTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//src/main/java/com/verlumen/tradestream/discovery:param_configs",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_constants",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:test_parameter_injector",
        "//third_party/java:truth",
    ],
)
