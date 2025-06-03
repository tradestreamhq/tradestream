load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "strategies_module",
    srcs = ["StrategiesModule.java"],
    deps = [
        ":strategy_factories",
        ":strategy_factory",
        ":strategy_manager",
        ":strategy_manager_impl",
        ":strategy_state",
        ":strategy_state_factory_impl",
        "//third_party/java:guava",
        "//third_party/java:guice",
    ],
)

java_library(
    name = "strategy_factories",
    srcs = ["StrategyFactories.java"],
    deps = [
        ":strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/momentumoscillators:oscillators_lib",
        "//src/main/java/com/verlumen/tradestream/strategies/movingaverages:movingaverages_lib",
        "//third_party/java:guava",
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

java_library(
    name = "strategy_manager",
    srcs = ["StrategyManager.java"],
    deps = [
        ":strategy_factory",
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "strategy_manager_impl",
    srcs = ["StrategyManagerImpl.java"],
    deps = [
        ":strategy_factory",
        ":strategy_manager",
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:mug",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)

kt_jvm_library(
    name = "strategy_processing_request",
    srcs = ["StrategyProcessingRequest.kt"],
    deps = [
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
    ],
)

java_library(
    name = "strategy_record",
    srcs = ["StrategyRecord.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "strategy_state",
    srcs = ["StrategyState.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "strategy_state_factory_impl",
    srcs = ["StrategyStateFactoryImpl.java"],
    deps = [
        ":strategy_manager",
        ":strategy_record",
        ":strategy_state",
        "//protos:strategies_java_proto",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)
