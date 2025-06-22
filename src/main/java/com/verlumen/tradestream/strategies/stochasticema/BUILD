load("@rules_java//java:defs.bzl", "java_library")

java_library(
    name = "param_config",
    srcs = ["StochasticEmaParamConfig.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
    visibility = ["//visibility:public"],
)

java_library(
    name = "strategy_factory",
    srcs = ["StochasticEmaStrategyFactory.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//third_party/java:guava",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
    visibility = ["//visibility:public"],
) 