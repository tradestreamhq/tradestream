java_library(
    name = "param_config",
    srcs = ["FibonacciRetracementsParamConfig.java"],
    visibility = ["//visibility:public"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "strategy_factory",
    srcs = ["FibonacciRetracementsStrategyFactory.java"],
    visibility = ["//visibility:public"],
    deps = [
        ":param_config",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//third_party/java:ta4j_core",
        "@com_google_protobuf//java/core",
        "@tradestream_maven//:com_google_protobuf_protobuf_java",
    ],
)
