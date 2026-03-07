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

java_test(
    name = "StrategyConfigLoaderTest",
    srcs = ["StrategyConfigLoaderTest.java"],
    test_class = "com.verlumen.tradestream.strategies.configurable.StrategyConfigLoaderTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:strategy_config_loader",
        "//third_party/java:junit",
    ],
)

java_test(
    name = "ConfigBasedVsHardcodedValidationTest",
    srcs = ["ConfigBasedVsHardcodedValidationTest.java"],
    test_class = "com.verlumen.tradestream.strategies.configurable.ConfigBasedVsHardcodedValidationTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:configurable_strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:strategy_config_loader",
        "//src/main/java/com/verlumen/tradestream/strategies/smaemacrossover:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
    ],
)

java_test(
    name = "RuleRegistryTest",
    srcs = ["RuleRegistryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.configurable.RuleRegistryTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:rule_registry",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "ResolvedParamsTest",
    srcs = ["ResolvedParamsTest.java"],
    test_class = "com.verlumen.tradestream.strategies.configurable.ResolvedParamsTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
)

test_suite(
    name = "all_tests",
    tests = [
        ":ConfigBasedVsHardcodedValidationTest",
        ":ConfigurableParamConfigTest",
        ":ConfigurableStrategyFactoryTest",
        ":IndicatorRegistryTest",
        ":ResolvedParamsTest",
        ":RuleRegistryTest",
        ":StrategyConfigLoaderTest",
    ],
)
