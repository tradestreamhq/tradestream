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
