proto_library(
    name = "backtesting_proto",
    srcs = ["backtesting.proto"],
    deps = [
        ":marketdata_proto",
        ":strategies_proto",
    ],
    visibility = ["//visibility:private"],
)

java_proto_library(
    name = "backtesting_java_proto",
    deps = [":backtesting_proto"],
    visibility = ["//:__subpackages__"],
)

proto_library(
    name = "marketdata_proto",
    srcs = ["marketdata.proto"],
    visibility = ["//visibility:private"],
)

java_proto_library(
    name = "marketdata_java_proto",
    deps = [":marketdata_proto"],
    visibility = ["//:__subpackages__"],
)

proto_library(
    name = "strategies_proto",
    srcs = ["strategies.proto"],
    visibility = ["//visibility:private"],
)

java_proto_library(
    name = "strategies_java_proto",
    deps = [":strategies_proto"],
    visibility = ["//:__subpackages__"],
)
