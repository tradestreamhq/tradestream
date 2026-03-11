load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "param_config_test",
    srcs = ["PriceOscillatorSignalParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.priceoscillatorsignal.PriceOscillatorSignalParamConfigTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/priceoscillatorsignal:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["PriceOscillatorSignalStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.priceoscillatorsignal.PriceOscillatorSignalStrategyFactoryTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/priceoscillatorsignal:strategy_factory",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "PriceOscillatorSignalConfigTest",
    srcs = ["PriceOscillatorSignalConfigTest.java"],
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
