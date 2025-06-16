load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

java_library(
    name = "param_config",
    srcs = ["IchimokuCloudParamConfig.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)
