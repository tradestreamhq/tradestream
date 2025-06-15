load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = [
        "//src/main/java/com/verlumen/tradestream/strategies:__subpackages__",
        "//src/test/java/com/verlumen/tradestream/strategies:__subpackages__"
    ]
)

java_library(
    name = "sma_rsi_param_config",
    srcs = ["SmaRsiParamConfig.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "sma_rsi_strategy_factory",
    srcs = ["SmaRsiStrategyFactory.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//third_party/java:guava",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)
