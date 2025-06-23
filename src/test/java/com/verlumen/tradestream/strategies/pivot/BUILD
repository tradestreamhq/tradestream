load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "param_config_test",
    srcs = ["PivotParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.pivot.PivotParamConfigTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/pivot:param_config",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["PivotStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.pivot.PivotStrategyFactoryTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/pivot:strategy_factory",
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
) 