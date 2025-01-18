load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("//platforms:transition.bzl", "multi_arch")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "backtest_runner",
    srcs = ["BacktestRunner.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//third_party:auto_value",
        "//third_party:guice",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "backtest_runner_impl",
    srcs = ["BacktestRunnerImpl.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:strategies_java_proto",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:ta4j_core",
        ":backtest_runner",
    ],
)

java_library(
    name = "backtest_service_client",
    srcs = ["BacktestServiceClient.java"],
    deps = [
        "//protos:backtesting_java_proto",
    ],
)

java_library(
    name = "backtest_service_client_impl",
    srcs = ["BacktestServiceClientImpl.java"],
    deps = [
        "//protos:backtesting_java_grpc",
        "//protos:backtesting_java_proto",
        "//third_party:guice",
        "//third_party:grpc_java_api",
        "//third_party:grpc_java_stub",
        ":backtest_service_client",
    ],
)

java_library(
    name = "backtest_service_impl",
    srcs = ["BacktestServiceImpl.java"],
    deps = [
        "//protos:backtesting_java_grpc",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager",
        "//third_party:guice",
        "//third_party:grpc_java_api",
        "//third_party:grpc_java_stub",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
        ":backtest_runner",
    ],
)

java_library(
    name = "backtesting_module",
    srcs = ["BacktestingModule.java"],
    deps = [
        "//protos:backtesting_java_grpc",
        "//src/main/java/com/verlumen/tradestream/grpc:endpoint",
        "//third_party:guice",
        ":backtest_service_client",
        ":backtest_service_client_impl",
        ":ga_service_client",
        ":ga_service_client_impl",
    ],
)

java_binary(
    name = "ga_server",
    srcs = ["GAServer.java"],
    main_class = "com.verlumen.tradestream.backtesting.GAServer",
    deps = [
        "//third_party:flogger",
        "//third_party:grpc_java_api",
        "//third_party:guice",
        ":backtesting_module",
        ":ga_service_impl",
    ],
)

container_structure_test(
    name = "ga_server_container_test",
    configs = ["ga-server-container-structure-test.yaml"],
    image = ":ga_server_image",
    tags = ["requires-docker"],
)

oci_image(
    name = "ga_server_image",
    base = "@openjdk_java",
    entrypoint = [
        "java",
        "-jar",
        "/src/main/java/com/verlumen/tradestream/backtesting/ga_server_deploy.jar",
    ],
    tars = [":ga_server_layer"],
)

multi_arch(
    name = "ga_server_images",
    image = ":ga_server_image",
    platforms = [
        "//platforms:linux_arm64",
        "//platforms:linux_amd64",
    ],
)

tar(
    name = "ga_server_layer",
    srcs = [":ga_server_deploy.jar"],
)

oci_image_index(
    name = "ga_server_index",
    images = [
        ":ga_server_images",
    ],
)

java_library(
    name = "ga_service_client",
    srcs = ["GAServiceClient.java"],
    deps = [
        "//protos:backtesting_java_proto",
    ],
)

java_library(
    name = "ga_service_client_impl",
    srcs = ["GAServiceClientImpl.java"],
    visibility = ["//visibility:public"],
    deps = [
        "//protos:backtesting_java_grpc",
        "//protos:backtesting_java_proto",
        "//third_party:guice",
        "//third_party:grpc_java_api",
        "//third_party:grpc_java_netty_shaded",
        "//third_party:grpc_java_stub",
        ":ga_service_client",
    ],
)

java_library(
    name = "ga_service_impl",
    srcs = ["GAServiceImpl.java"],
    deps = [
        "//protos:backtesting_java_grpc",
        "//protos:backtesting_java_proto",
        "//third_party:grpc_java_api",
        "//third_party:grpc_java_stub",
        "//third_party:guice",
        ":genetic_algorithm_orchestrator",
    ],
)

java_library(
    name = "genetic_algorithm_orchestrator",
    srcs = ["GeneticAlgorithmOrchestrator.java"],
    deps = [
        "//protos:backtesting_java_proto",
    ],
)

java_library(
    name = "genetic_algorithm_orchestrator_impl",
    srcs = ["GeneticAlgorithmOrchestratorImpl.java"],
    deps = [
        "//protos:backtesting_java_grpc",
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto", 
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting/params:params_lib",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:jenetics",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
        ":backtest_service_client",
        ":genetic_algorithm_orchestrator",
    ],
)

oci_push(
    name = "push_ga_server_image",
    image = ":ga_server_index",
    remote_tags = ["latest"],
    repository = "tradestreamhq/tradestream-ga-server",
)

