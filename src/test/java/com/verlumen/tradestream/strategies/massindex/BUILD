java_test(
    name = "param_config_test",
    srcs = ["MassIndexParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.massindex.MassIndexParamConfigTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/massindex:param_config",
        "//protos:strategies_java_proto",
        "//third_party/java:junit",
        "//third_party/java:truth",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["MassIndexStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.massindex.MassIndexStrategyFactoryTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/massindex:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/ta4j:test_bar_series_builder",
        "//protos:strategies_java_proto",
        "//third_party/java:junit",
        "//third_party/java:truth",
        "//third_party/java:ta4j_core",
        "//third_party/java:protobuf_java",
    ],
)
