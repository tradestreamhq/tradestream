package(default_visibility = ["//src:__subpackages__"])

java_library(
    name = "momentumsmarrossover_strategy_lib",
    srcs = glob(["*.java"]),
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/movingaverages:movingaverages_lib", # For MomentumIndicator
        "//third_party/java:guava",
        "//third_party/java:jenetics", # For NumericChromosome in ParamConfig
        "//third_party/java:ta4j_core",
    ],
)
