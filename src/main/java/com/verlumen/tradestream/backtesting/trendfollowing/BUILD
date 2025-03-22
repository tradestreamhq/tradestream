load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "ichimoku_cloud_param_config",
    srcs = ["IchimokuCloudParamConfig.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/backtesting:param_config",
        "//third_party:guava",
        "//third_party:jenetics",
        "//third_party:protobuf_java",
    ],
)

kt_jvm_library(
    name = "trend_following_params",
    srcs = ["TrendFollowingParams.kt"],
    deps = [
        ":ichimoku_cloud_param_config",
        "//src/main/java/com/verlumen/tradestream/backtesting:param_config",
    ],
)
