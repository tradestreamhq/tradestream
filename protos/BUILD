load("@io_grpc_grpc_java//:java_grpc_library.bzl", "java_grpc_library")

package(
    default_visibility = ["//visibility:public"]
)

java_grpc_library(
    name = "backtesting_java_grpc",
    srcs = [":backtesting_proto"],
    deps = [":backtesting_java_proto"],
)

proto_library(
    name = "backtesting_proto",
    srcs = ["backtesting.proto"],
    deps = [
        "@com_google_protobuf//:any_proto",
        ":marketdata_proto",
        ":strategies_proto",
    ],
    visibility = ["//visibility:private"],
)

java_proto_library(
    name = "backtesting_java_proto",
    deps = [":backtesting_proto"],
)

proto_library(
    name = "marketdata_proto",
    srcs = ["marketdata.proto"],
    visibility = ["//visibility:private"],
)

java_proto_library(
    name = "marketdata_java_proto",
    deps = [":marketdata_proto"],
)

proto_library(
    name = "strategies_proto",
    srcs = ["strategies.proto"],
    visibility = ["//visibility:private"],
)

java_proto_library(
    name = "strategies_java_proto",
    deps = [":strategies_proto"],
)
