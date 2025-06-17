load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = [
  "//src/test/java/com/verlumen/tradestream/strategies/tripleemacrossover:__pkg__",],)

java_library(
    name = "strategy_factory",
    srcs = ["TripleEmaCrossoverStrategyFactory.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//third_party/java:guava",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)
