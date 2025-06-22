load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "param_config_test",
    srcs = ["MomentumPinballParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.momentumpinball.MomentumPinballParamConfigTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/momentumpinball:param_config",
        "//third_party/java:junit",
        "//protos:strategies_java_proto",
        "//third_party/java:protobuf_java",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["MomentumPinballStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.momentumpinball.MomentumPinballStrategyFactoryTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/momentumpinball:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
        "//protos:strategies_java_proto",
        "//third_party/java:protobuf_java",
    ],
) 