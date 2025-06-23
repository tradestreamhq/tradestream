java_test(
    name = "param_config_test",
    srcs = ["RangeBarsParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.rangebars.RangeBarsParamConfigTest",
    visibility = ["//visibility:public"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/rangebars:param_config",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["RangeBarsStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.rangebars.RangeBarsStrategyFactoryTest",
    visibility = ["//visibility:public"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/rangebars:strategy_factory",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//third_party/java:ta4j_core",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
) 