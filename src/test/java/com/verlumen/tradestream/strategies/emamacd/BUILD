load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "EmaMacdParamConfigTest",
    srcs = ["EmaMacdParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.emamacd.EmaMacdParamConfigTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//src/main/java/com/verlumen/tradestream/strategies/emamacd:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)
