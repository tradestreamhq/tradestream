load("@rules_java//java:defs.bzl", "java_binary")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

kt_jvm_library(
    name = "backtesting_grpc_service",
    srcs = ["BacktestingGrpcService.kt"],
    deps = [
        "//protos:backtesting_java_grpc",
        "//protos:backtesting_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//src/main/java/com/verlumen/tradestream/backtesting:strategy_validator",
        "//src/main/java/com/verlumen/tradestream/backtesting:walk_forward_runner",
        "//third_party/java:flogger",
        "//third_party/java:grpc_stub",
        "//third_party/java:guice",
    ],
)

kt_jvm_library(
    name = "backtesting_service_module",
    srcs = ["BacktestingServiceModule.kt"],
    deps = [
        ":backtesting_grpc_service",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtesting_module",
        "//third_party/java:guice",
    ],
)

kt_jvm_library(
    name = "backtest_service_server_lib",
    srcs = ["BacktestServiceServer.kt"],
    deps = [
        ":backtesting_grpc_service",
        ":backtesting_service_module",
        "//third_party/java:argparse4j",
        "//third_party/java:flogger",
        "//third_party/java:grpc_netty_shaded",
        "//third_party/java:grpc_services",
        "//third_party/java:guice",
    ],
)

java_binary(
    name = "backtest_service_server",
    main_class = "com.verlumen.tradestream.backtestingservice.BacktestServiceServer",
    runtime_deps = [
        ":backtest_service_server_lib",
        ":backtesting_service_module",
    ],
)
