load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "param_config_test",
    srcs = ["StochasticEmaParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.stochasticema.StochasticEmaParamConfigTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/stochasticema:param_config",
        "//third_party/java:junit",
        "//third_party/java:truth",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//protos:strategies_java_proto",
        "//third_party/java:protobuf_java",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["StochasticEmaStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.stochasticema.StochasticEmaStrategyFactoryTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/stochasticema:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
        "//protos:strategies_java_proto",
        "//third_party/java:protobuf_java",
    ],
) 