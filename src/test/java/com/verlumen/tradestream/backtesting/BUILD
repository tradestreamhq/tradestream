load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "FitnessFunctionFactoryImplTest",
    size = "small",
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
        "//protos:marketdata_java_proto",  # Added for Candle
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:fitness_function_factory",
        "//src/main/java/com/verlumen/tradestream/discovery:ga_engine_factory",
        "//src/main/java/com/verlumen/tradestream/discovery:ga_engine_factory_impl",
        "//src/main/java/com/verlumen/tradestream/discovery:ga_engine_params",  # Added
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config_manager",
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
    size = "small",
    srcs = ["GenotypeConverterImplTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
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
