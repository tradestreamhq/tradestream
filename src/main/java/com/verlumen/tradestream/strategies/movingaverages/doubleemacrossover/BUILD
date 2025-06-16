package(default_visibility = ["//src:__subpackages__"])

java_library(
    name = "doubleemacrossover_strategy_lib",
    srcs = glob(["*.java"]),
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config", # For ParamConfig
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory", # For StrategyFactory
        # "//src/main/java/com/verlumen/tradestream/strategies/movingaverages", # Not needed as MomentumIndicator not used by DoubleEmaCrossoverStrategyFactory
        "//third_party/java:guava", # For Preconditions in Factory and ImmutableList in ParamConfig
        "//third_party/java:jenetics", # For NumericChromosome in ParamConfig (even if not fully implemented)
        "//third_party/java:ta4j_core", # For ta4j classes in Factory
    ],
)
