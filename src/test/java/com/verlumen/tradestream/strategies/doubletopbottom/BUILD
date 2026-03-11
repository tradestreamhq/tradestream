load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "DoubleTopBottomConfigTest",
    srcs = ["DoubleTopBottomConfigTest.java"],
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

java_test(
    name = "param_config_test",
    srcs = ["DoubleTopBottomParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.doubletopbottom.DoubleTopBottomParamConfigTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/doubletopbottom:param_config",
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
    srcs = ["DoubleTopBottomStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.doubletopbottom.DoubleTopBottomStrategyFactoryTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/doubletopbottom:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
        "@com_google_protobuf//java/core",
        "@tradestream_maven//:com_google_protobuf_protobuf_java",
    ],
)
