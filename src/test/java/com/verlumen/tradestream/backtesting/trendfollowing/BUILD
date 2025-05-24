load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "IchimokuCloudParamConfigTest",
    srcs = ["IchimokuCloudParamConfigTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/backtesting/trendfollowing:ichimoku_cloud_param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)
