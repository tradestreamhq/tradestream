load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "param_config_test",
    srcs = ["LinearRegressionChannelsParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.linearregressionchannels.LinearRegressionChannelsParamConfigTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/linearregressionchannels:param_config",
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
    srcs = ["LinearRegressionChannelsStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.linearregressionchannels.LinearRegressionChannelsStrategyFactoryTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/linearregressionchannels:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:truth",
        "//third_party/java:ta4j_core",
        "//protos:strategies_java_proto",
        "//third_party/java:protobuf_java",
    ],
) 