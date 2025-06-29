java_test(
    name = "param_config_test",
    srcs = ["VariablePeriodEmaParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.variableperiodema.VariablePeriodEmaParamConfigTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/variableperiodema:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["VariablePeriodEmaStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.variableperiodema.VariablePeriodEmaStrategyFactoryTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/variableperiodema:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/variableperiodema:strategy_factory",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
