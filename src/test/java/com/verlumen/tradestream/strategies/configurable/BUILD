load("@rules_java//java:defs.bzl", "java_test")

package(default_visibility = ["//visibility:public"])

java_test(
    name = "ConfigurableStrategyFactoryTest",
    srcs = ["ConfigurableStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.configurable.ConfigurableStrategyFactoryTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:configurable_strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
    ],
)

java_test(
    name = "ConfigurableParamConfigTest",
    srcs = ["ConfigurableParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.configurable.ConfigurableParamConfigTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:configurable_param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
    ],
)

java_test(
    name = "IndicatorRegistryTest",
    srcs = ["IndicatorRegistryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.configurable.IndicatorRegistryTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:indicator_registry",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
    ],
)

test_suite(
    name = "all_tests",
    tests = [
        ":ConfigurableParamConfigTest",
        ":ConfigurableStrategyFactoryTest",
        ":IndicatorRegistryTest",
    ],
)
