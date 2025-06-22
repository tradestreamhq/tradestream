java_test(
    name = "param_config_test",
    srcs = ["VptParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.vpt.VptParamConfigTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/strategies/vpt:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["VptStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.vpt.VptStrategyFactoryTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/vpt:strategy_factory",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
