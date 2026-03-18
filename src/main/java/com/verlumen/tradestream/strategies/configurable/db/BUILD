load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "config_driven_strategy_builder",
    srcs = ["ConfigDrivenStrategyBuilder.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:configurable_strategy_factory",
        "//third_party/java:gson",
        "//third_party/java:ta4j_core",
    ],
)
