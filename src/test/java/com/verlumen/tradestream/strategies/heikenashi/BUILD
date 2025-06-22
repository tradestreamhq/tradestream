load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "HeikenAshiParamConfigTest",
    srcs = ["HeikenAshiParamConfigTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/strategies/heikenashi:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "HeikenAshiStrategyFactoryTest",
    srcs = ["HeikenAshiStrategyFactoryTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/heikenashi:strategy_factory",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)