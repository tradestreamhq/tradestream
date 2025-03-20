load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "AdxStochasticParamConfigTest",
    srcs = ["AdxStochasticParamConfigTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/backtesting/momentumoscillators:adx_stochastic_param_config",
        "//third_party:guava",
        "//third_party:jenetics",
        "//third_party:junit",
        "//third_party:protobuf_java",
        "//third_party:truth",
    ],
)

java_test(
    name = "SmaRsiParamConfigTest",
    size = "small",
    srcs = ["SmaRsiParamConfigTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/backtesting/momentumoscillators:sma_rsi_param_config",
        "//third_party:guava",
        "//third_party:jenetics",
        "//third_party:junit",
        "//third_party:truth",
    ],
)
