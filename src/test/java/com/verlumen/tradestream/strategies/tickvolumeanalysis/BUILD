java_test(
    name = "param_config_test",
    srcs = ["TickVolumeAnalysisParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.tickvolumeanalysis.TickVolumeAnalysisParamConfigTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/strategies/tickvolumeanalysis:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["TickVolumeAnalysisStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.tickvolumeanalysis.TickVolumeAnalysisStrategyFactoryTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/tickvolumeanalysis:strategy_factory",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
