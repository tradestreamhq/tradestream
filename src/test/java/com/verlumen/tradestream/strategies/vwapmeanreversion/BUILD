java_test(
    name = "param_config_test",
    srcs = ["VwapMeanReversionParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.vwapmeanreversion.VwapMeanReversionParamConfigTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/vwapmeanreversion:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["VwapMeanReversionStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.vwapmeanreversion.VwapMeanReversionStrategyFactoryTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/vwapmeanreversion:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
