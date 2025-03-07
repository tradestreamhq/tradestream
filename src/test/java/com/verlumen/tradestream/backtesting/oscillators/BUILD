load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "SmaRsiParamConfigTest",
    size = "small",
    srcs = ["SmaRsiParamConfigTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/backtesting/oscillators:sma_rsi_param_config",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:jenetics",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:truth",
    ],
)
