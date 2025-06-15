load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "SmaRsiParamConfigTest",
    size = "small",
    srcs = ["SmaRsiParamConfigTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting/momentumoscillators:sma_rsi_param_config",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
)
