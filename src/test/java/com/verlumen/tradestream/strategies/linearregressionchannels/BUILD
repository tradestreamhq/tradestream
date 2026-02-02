load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "LinearRegressionChannelsConfigTest",
    srcs = ["LinearRegressionChannelsConfigTest.java"],
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

java_test(
    name = "param_config_test",
    srcs = ["LinearRegressionChannelsParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.linearregressionchannels.LinearRegressionChannelsParamConfigTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/linearregressionchannels:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["LinearRegressionChannelsStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.linearregressionchannels.LinearRegressionChannelsStrategyFactoryTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/linearregressionchannels:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
