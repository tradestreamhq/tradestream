load("@rules_java//java:defs.bzl", "java_library")

java_library(
    name = "ema_macd_param_config",
    srcs = ["EmaMacdParamConfig.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)
