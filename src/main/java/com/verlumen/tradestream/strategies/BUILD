load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

kt_jvm_library(
    name = "momentum_indicator",
    srcs = ["MomentumIndicator.kt"],
    deps = [
        "//third_party/java:ta4j_core",
    ],
)

kt_jvm_library(
    name = "strategies_module",
    srcs = ["StrategiesModule.kt"],
    deps = [
        ":strategy_factory",
        "//third_party/java:guava",
        "//third_party/java:guice",
    ],
)

kt_jvm_library(
    name = "strategy_constants",
    srcs = ["StrategyConstants.kt"],
    deps = [
        "//protos:strategies_java_proto",
    ],
)

java_library(
    name = "strategy_factory",
    srcs = ["StrategyFactory.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)

kt_jvm_library(
    name = "strategy_specs",
    srcs = [
        "StrategySpec.kt",
        "StrategySpecs.kt",
    ],
    visibility = ["//visibility:public"],
    deps = [
        # Core interfaces required by the spec definitions
        ":strategy_factory",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",

        # Implementations for each strategy included in the map
        "//src/main/java/com/verlumen/tradestream/strategies/adxstochastic:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/adxstochastic:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/emamacd:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/emamacd:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/smarsi:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/smarsi:strategy_factory",
    ],
)
