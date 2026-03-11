load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "SarMfiConfigTest",
    srcs = ["SarMfiConfigTest.java"],
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
    name = "SarMfiParamConfigTest",
    srcs = ["SarMfiParamConfigTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/strategies/sarmfi:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "SarMfiStrategyFactoryTest",
    srcs = ["SarMfiStrategyFactoryTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/sarmfi:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
