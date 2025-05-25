load("@rules_python//python:proto.bzl", "py_proto_library")

proto_library(
    name = "backtesting_proto",
    srcs = ["backtesting.proto"],
    deps = [
        ":marketdata_proto",
        ":strategies_proto",
        "@com_google_protobuf//:any_proto",
    ],
)

java_proto_library(
    name = "backtesting_java_proto",
    visibility = ["//visibility:public"],
    deps = [":backtesting_proto"],
)

py_proto_library(
    name = "backtesting_py_proto",
    visibility = ["//visibility:public"],
    deps = [":backtesting_proto"],
)

proto_library(
    name = "discovery_proto",
    srcs = ["discovery.proto"],
    deps = [
        ":strategies_proto",
        "@com_google_protobuf//:timestamp_proto",
    ],
)

py_proto_library(
    name = "discovery_py_proto",
    visibility = ["//visibility:public"],
    deps = [":discovery_proto"],
)

proto_library(
    name = "marketdata_proto",
    srcs = ["marketdata.proto"],
    deps = [
        "@com_google_protobuf//:timestamp_proto",
    ],
)

java_proto_library(
    name = "marketdata_java_proto",
    visibility = ["//visibility:public"],
    deps = [":marketdata_proto"],
)

py_proto_library(
    name = "marketdata_py_proto",
    visibility = ["//visibility:public"],
    deps = [":marketdata_proto"],
)

proto_library(
    name = "strategies_proto",
    srcs = ["strategies.proto"],
    deps = [
        "@com_google_protobuf//:any_proto",
    ],
)

java_proto_library(
    name = "strategies_java_proto",
    visibility = ["//visibility:public"],
    deps = [":strategies_proto"],
)

py_proto_library(
    name = "strategies_py_proto",
    visibility = ["//visibility:public"],
    deps = [":strategies_proto"],
)

proto_library(
    name = "trade_signals_proto",
    srcs = ["trade_signals.proto"],
    deps = [
        ":strategies_proto",
    ],
)

java_proto_library(
    name = "trade_signals_java_proto",
    visibility = ["//visibility:public"],
    deps = [":trade_signals_proto"],
)
