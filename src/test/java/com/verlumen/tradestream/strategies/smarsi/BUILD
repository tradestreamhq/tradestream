load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "SmaRsiStrategyFactoryTest",
    srcs = ["SmaRsiStrategyFactoryTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/momentumoscillators:oscillators_lib",
        "//third_party/java:flogger",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "SmaRsiParamConfigTest",
    size = "small",
    srcs = ["SmaRsiParamConfigTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/strategies/smarsi:sma_rsi_param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
)
