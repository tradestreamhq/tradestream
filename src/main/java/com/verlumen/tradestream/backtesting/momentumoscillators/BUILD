load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

kt_jvm_library(
    name = "momentum_oscillator_params",
    srcs = ["MomentumOscillatorParams.kt"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/discovery:param_config",
    ],
)
