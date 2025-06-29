load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "ChaikinOscillatorParamConfigTest",
    srcs = ["ChaikinOscillatorParamConfigTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/strategies/chaikinoscillator:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "ChaikinOscillatorStrategyFactoryTest",
    srcs = ["ChaikinOscillatorStrategyFactoryTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/chaikinoscillator:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
