load("@rules_java//java:defs.bzl", "java_test")

package(default_visibility = ["//visibility:public"])

java_test(
    name = "StrategySpecPromptTemplateTest",
    srcs = ["StrategySpecPromptTemplateTest.java"],
    test_class = "com.verlumen.tradestream.strategies.configurable.llm.StrategySpecPromptTemplateTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable/llm:prompt_template",
        "//third_party/java:junit",
    ],
)

java_test(
    name = "GeneratedSpecValidatorTest",
    srcs = ["GeneratedSpecValidatorTest.java"],
    test_class = "com.verlumen.tradestream.strategies.configurable.llm.GeneratedSpecValidatorTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable/llm:generated_spec_validator",
        "//third_party/java:junit",
    ],
)

java_test(
    name = "BacktestPipelineTest",
    srcs = ["BacktestPipelineTest.java"],
    test_class = "com.verlumen.tradestream.strategies.configurable.llm.BacktestPipelineTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable/llm:backtest_pipeline",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
    ],
)
