load("@grpc//bazel:python_rules.bzl", "py_grpc_library", "py_proto_library")
load("@io_grpc_grpc_java//:java_grpc_library.bzl", "java_grpc_library")

proto_library(
    name = "backtesting_proto",
    srcs = ["backtesting.proto"],
    deps = [
        "@com_google_protobuf//:any_proto",
        ":marketdata_proto",
        ":strategies_proto",
    ],
)

java_grpc_library(
    name = "backtesting_java_grpc",
    visibility = ["//visibility:public"],
    srcs = [":backtesting_proto"],
    deps = [":backtesting_java_proto"],
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

py_grpc_library(
    name = "backtesting_py_grpc",
    visibility = ["//visibility:public"],
    srcs = [":backtesting_proto"],
    deps = [":backtesting_py_proto"],
)

proto_library(
    name = "marketdata_proto",
    srcs = ["marketdata.proto"],
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
