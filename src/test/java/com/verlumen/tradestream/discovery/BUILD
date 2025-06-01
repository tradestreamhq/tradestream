load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_test")

package(default_visibility = ["//visibility:public"])

kt_jvm_test(
    name = "DeserializeStrategyDiscoveryRequestFnTest",
    srcs = ["DeserializeStrategyDiscoveryRequestFnTest.kt"],
    test_class = "com.verlumen.tradestream.discovery.DeserializeStrategyDiscoveryRequestFnTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/discovery:strategy_discovery_pipeline_lib",
        "//protos:discovery_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils", # For PAssert and TestPipeline
        "//third_party/java:junit",
        "//third_party/java:truth", # ForassertThat
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
        # "//src/main/java/com/verlumen/tradestream/backtesting:fitness_calculator", # Ensure this target exists
        "//src/main/java/com/verlumen/tradestream/marketdata:influxdb_candle_fetcher",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:junit",
        "//third_party/java:truth",
        "//third_party/java:mockito_core",
        "//third_party/kotlin:mockito_kotlin", # For Kotlin idiomatic mocking
        "//third_party/java:jenetics",
        "//third_party/kotlin:kotlin_stdlib",
    ],
)

kt_jvm_test(
    name = "ExtractDiscoveredStrategiesFnTest",
    srcs = ["ExtractDiscoveredStrategiesFnTest.kt"],
    test_class = "com.verlumen.tradestream.discovery.ExtractDiscoveredStrategiesFnTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/discovery:strategy_discovery_pipeline_lib",
        "//protos:discovery_java_proto",
        "//protos:strategies_java_proto", # For StrategyType and SmaRsiParameters
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:junit",
        "//third_party/java:truth",
        "//third_party/java:protobuf_java_util", # For Timestamps
        "//third_party/kotlin:kotlin_stdlib",
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
        "//third_party/java:protobuf_java_util", // For JsonFormat if used in test
        "//third_party/kotlin:kotlin_stdlib",
    ],
)
