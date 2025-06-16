load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

kt_jvm_library(
    name = "moving_average_params",
    srcs = ["MovingAverageParams.kt"],
    deps = [
        ":ema_macd_param_config",
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
    ],
)
