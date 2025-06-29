load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "AroonMfiParamConfigTest",
    srcs = ["AroonMfiParamConfigTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/strategies/aroonmfi:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "AroonMfiStrategyFactoryTest",
    srcs = ["AroonMfiStrategyFactoryTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/aroonmfi:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
