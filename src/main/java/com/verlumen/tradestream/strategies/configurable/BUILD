load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "config_pojos",
    srcs = [
        "ConditionConfig.java",
        "IndicatorConfig.java",
        "ParameterDefinition.java",
        "ParameterType.java",
        "ResolvedParams.java",
        "StrategyConfig.java",
    ],
)

java_library(
    name = "indicator_registry",
    srcs = [
        "IndicatorFactory.java",
        "IndicatorRegistry.java",
        "MassIndexIndicator.java",
        "PreviousValueIndicator.java",
    ],
    deps = [
        ":config_pojos",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "rule_registry",
    srcs = [
        "RuleFactory.java",
        "RuleRegistry.java",
    ],
    deps = [
        ":config_pojos",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "configurable_strategy_factory",
    srcs = ["ConfigurableStrategyFactory.java"],
    deps = [
        ":config_pojos",
        ":indicator_registry",
        ":rule_registry",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "configurable_param_config",
    srcs = ["ConfigurableParamConfig.java"],
    deps = [
        ":config_pojos",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "strategy_config_loader",
    srcs = ["StrategyConfigLoader.java"],
    resources = ["//src/main/resources:strategies"],
    deps = [
        ":config_pojos",
        "//third_party/java:gson",
        "//third_party/java:snakeyaml",
    ],
)

java_library(
    name = "configurable_strategy_spec",
    srcs = ["ConfigurableStrategySpec.java"],
    deps = [
        ":config_pojos",
        ":configurable_param_config",
        ":configurable_strategy_factory",
        ":strategy_config_loader",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_specs",
    ],
)

# Convenience target that bundles everything
java_library(
    name = "configurable",
    exports = [
        ":config_pojos",
        ":configurable_param_config",
        ":configurable_strategy_factory",
        ":configurable_strategy_spec",
        ":indicator_registry",
        ":rule_registry",
        ":strategy_config_loader",
    ],
)
