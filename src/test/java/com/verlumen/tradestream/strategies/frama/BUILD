load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "param_config_test",
    srcs = ["FramaParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.frama.FramaParamConfigTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/frama:param_config",
        "//protos:strategies_java_proto",
        "//third_party/java:jenetics",
        "//third_party/java:truth",
        "//third_party/java:protobuf_java",
        "//third_party/java:junit",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//third_party/java:guava",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["FramaStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.frama.FramaStrategyFactoryTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/frama:strategy_factory",
        "//protos:strategies_java_proto",
        "//third_party/java:truth",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
    ],
) 