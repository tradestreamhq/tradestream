load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "param_config_test",
    srcs = ["MomentumPinballParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.momentumpinball.MomentumPinballParamConfigTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/momentumpinball:param_config",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["MomentumPinballStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.momentumpinball.MomentumPinballStrategyFactoryTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/momentumpinball:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/ta4j:momentum_indicator",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "MomentumPinballConfigTest",
    srcs = ["MomentumPinballConfigTest.java"],
    resources = ["//src/main/resources:strategies"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/strategies/configurable",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
