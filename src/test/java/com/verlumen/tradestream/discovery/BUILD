load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "GenotypeConverterImplTest",
    size = "small",
    srcs = ["GenotypeConverterImplTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/backtesting:param_config",
        "//src/main/java/com/verlumen/tradestream/backtesting:param_config_manager",
        "//src/main/java/com/verlumen/tradestream/discovery:genotype_converter",
        "//src/main/java/com/verlumen/tradestream/discovery:genotype_converter_impl",
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
