load("@io_grpc_grpc_java//:java_grpc_library.bzl", "java_grpc_library")
load("@rules_proto_grpc_python//:defs.bzl", "python_grpc_library", "python_proto_library")

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

python_proto_library(
    name = "backtesting_py_proto",
    visibility = ["//visibility:public"],
    protos = [":backtesting_proto"],
)

python_grpc_library(
    name = "backtesting_py_grpc",
    visibility = ["//visibility:public"],
    protos = [":backtesting_proto"],
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

python_proto_library(
    name = "marketdata_py_proto",
    visibility = ["//visibility:public"],
    protos = [":marketdata_proto"],
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

python_proto_library(
    name = "strategies_py_proto",
    visibility = ["//visibility:public"],
    protos = [":strategies_proto"],
)
