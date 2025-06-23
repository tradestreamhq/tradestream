java_test(
    name = "param_config_test",
    srcs = ["PriceGapParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.pricegap.PriceGapParamConfigTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/pricegap:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
        "@com_google_protobuf//java/core",
        "@tradestream_maven//:com_google_protobuf_protobuf_java",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["PriceGapStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.pricegap.PriceGapStrategyFactoryTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/pricegap:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
        "@com_google_protobuf//java/core",
        "@tradestream_maven//:com_google_protobuf_protobuf_java",
    ],
)
