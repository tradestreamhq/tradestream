load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")
load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "adx_stochastic_param_config",
    srcs = ["AdxStochasticParamConfig.java"],
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
    name = "momentum_oscillator_params",
    srcs = ["MomentumOscillatorParams.kt"],
    deps = [
        ":adx_stochastic_param_config",
        ":sma_rsi_param_config",
        "//src/main/java/com/verlumen/tradestream/backtesting:param_config",
    ],
)

java_library(
    name = "sma_rsi_param_config",
    srcs = ["SmaRsiParamConfig.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:chromosome_spec",
        "//src/main/java/com/verlumen/tradestream/backtesting:param_config",
        "//third_party:guava",
        "//third_party:jenetics",
        "//third_party:protobuf_java",
    ],
)
