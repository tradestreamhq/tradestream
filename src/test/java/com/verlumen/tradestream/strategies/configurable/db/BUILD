load("@rules_java//java:defs.bzl", "java_test")

package(default_visibility = ["//visibility:public"])

java_test(
    name = "ConfigDrivenStrategyBuilderTest",
    srcs = ["ConfigDrivenStrategyBuilderTest.java"],
    test_class = "com.verlumen.tradestream.strategies.configurable.db.ConfigDrivenStrategyBuilderTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable/db:config_driven_strategy_builder",
        "//third_party/java:gson",
        "//third_party/java:h2",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
