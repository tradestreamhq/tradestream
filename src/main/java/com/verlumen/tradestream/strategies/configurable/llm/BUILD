load("@rules_java//java:defs.bzl", "java_binary", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "openrouter_client",
    srcs = ["OpenRouterClient.java"],
    deps = [
        "//third_party/java:gson",
    ],
)

java_library(
    name = "prompt_template",
    srcs = ["StrategySpecPromptTemplate.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:strategy_config_loader",
    ],
)

java_library(
    name = "generated_spec_validator",
    srcs = ["GeneratedSpecValidator.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:indicator_registry",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:rule_registry",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:strategy_config_loader",
    ],
)

java_library(
    name = "backtest_pipeline",
    srcs = ["BacktestPipeline.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:configurable_strategy_factory",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "experiment_runner",
    srcs = ["ExperimentRunner.java"],
    deps = [
        ":backtest_pipeline",
        ":generated_spec_validator",
        ":openrouter_client",
        ":prompt_template",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:strategy_config_loader",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "results_storage",
    srcs = ["ResultsStorage.java"],
    deps = [
        ":backtest_pipeline",
        ":experiment_runner",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:strategy_config_loader",
        "//third_party/java:gson",
    ],
)

java_binary(
    name = "llm_spec_generation_experiment",
    srcs = ["LlmSpecGenerationExperiment.java"],
    main_class = "com.verlumen.tradestream.strategies.configurable.llm.LlmSpecGenerationExperiment",
    deps = [
        ":backtest_pipeline",
        ":experiment_runner",
        ":openrouter_client",
        ":results_storage",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:config_pojos",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable:strategy_config_loader",
        "//third_party/java:ta4j_core",
    ],
)

# Convenience target
java_library(
    name = "llm",
    exports = [
        ":backtest_pipeline",
        ":experiment_runner",
        ":generated_spec_validator",
        ":openrouter_client",
        ":prompt_template",
        ":results_storage",
    ],
)
