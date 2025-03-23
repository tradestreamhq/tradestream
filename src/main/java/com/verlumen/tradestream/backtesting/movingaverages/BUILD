load("@rules_java//java:defs.bzl", "java_library", "java_binary")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "ema_macd_param_config",
    srcs = ["EmaMacdParamConfig.java"],
    resources =
        ["//src/main/resources/com/verlumen/tradestream/backtesting/movingaverages:EmaMacdParamConfig.properties"],  # Add resource
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
    name = "moving_average_params",
    srcs = ["MovingAverageParams.kt"],
    deps = [
        ":ema_macd_param_config",
        "//src/main/java/com/verlumen/tradestream/backtesting:param_config",
    ],
)
