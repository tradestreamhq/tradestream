load("@rules_java//java:defs.bzl", "java_library")

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

java_library(
  name = "trendfollowing_params",
  srcs = ["TrendFollowingParams.java"],
  deps = [
      ":ichimoku_cloud_param_config",
      "//src/main/java/com/verlumen/tradestream/backtesting:param_config",
      "//third_party:guava",
  ]
)
