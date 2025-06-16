package(default_visibility = ["//src:__subpackages__"])

java_library(
    name = "ichimokucloud_strategy_lib",
    srcs = glob(["*.java"]),
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config", # For ParamConfig interface
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory", # For StrategyFactory interface
        "//third_party/java:guava", # For ImmutableList in ParamConfig
        "//third_party/java:jenetics", # For NumericChromosome in ParamConfig base
        "//third_party/java:ta4j_core", # For BarSeries, Strategy in Factory
    ],
)
