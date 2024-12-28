java_library(
    name = "param_config",
    srcs = ["ParamConfig.java"],
    deps = [
        "//third_party:auto_value",
        "//third_party:guava",
        "//third_party:jenetics",
        "//third_party:protobuf_java",
    ],
)

java_library(
    name = "sma_rsi_param_config",
    srcs = ["SmaRsiParamConfig.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party:guava",
        "//third_party:jenetics",
        "//third_party:protobuf_java",
        ":param_config",
    ],
)
