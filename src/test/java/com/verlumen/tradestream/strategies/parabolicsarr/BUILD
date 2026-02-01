load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "ParabolicSarConfigTest",
    srcs = ["ParabolicSarConfigTest.java"],
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
    name = "ParabolicSarParamConfigTest",
    srcs = ["ParabolicSarParamConfigTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/strategies/parabolicsarr:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "ParabolicSarStrategyFactoryTest",
    srcs = ["ParabolicSarStrategyFactoryTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/parabolicsarr:strategy_factory",
        "//third_party/java:flogger",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
