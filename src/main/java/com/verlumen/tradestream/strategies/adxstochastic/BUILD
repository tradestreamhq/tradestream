load("@rules_java//java:defs.bzl", "java_library")

package(
    default_visibility = [
        "//src/test/java/com/verlumen/tradestream/strategies:__pkg__",
    ],
)

java_library(
    name = "param_config",
    srcs = ["AdxStochasticParamConfig.java"],
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
    name = "strategy_factory",
    srcs = ["AdxStochasticStrategyFactory.java"],
    deps = [
        ":strategy_factory",
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)
