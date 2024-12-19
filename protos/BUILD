load("@io_grpc_grpc_java//:java_grpc_library.bzl", "java_grpc_library")

java_proto_library(
    name = "any_java_proto",
    deps = ["@com_google_protobuf//:any_proto"],
)

proto_library(
    name = "backtest_service_proto",
    srcs = ["backtest_service.proto"],
    deps = [
        ":backtesting_proto",
    ],
)

java_proto_library(
    name = "backtest_service_java_proto",
    deps = [":backtest_service_proto"],
    visibility = ["//:__subpackages__"],
)

java_grpc_library(
    name = "backtest_service_java_grpc",
    srcs = [":backtest_service_proto"],
    deps = [":backtest_service_java_proto"],
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
