load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility=[
    "//src/main/java/com/verlumen/tradestream/strategies:__pkg__",
      "//src/test/java/com/verlumen/tradestream/strategies/doubleemacrossover:__pkg__",
])

java_library(
  name = "strategy_factory",
  srcs = ["DoubleEmaCrossoverStrategyFactory.java"],
  deps = [
    "//protos:strategies_java_proto",
    "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
    "//third_party/java:protobuf_java",
    "//third_party/java:ta4j_core",
  ]
)
