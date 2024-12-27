load("@rules_java//java:defs.bzl", "java_library")
load("@rules_java//java:defs.bzl", "java_binary")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_push")
load("@container_structure_test//:defs.bzl", "container_structure_test")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "ga_service_module",
    srcs = [
        "GAServiceModule.java",
        "GAServiceImpl.java",
    ],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:ga_java_grpc",
        "//protos:ga_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",  # or your actual backtest library
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager",
        "//third_party:flogger",
        "//third_party:flogger_system_backend",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:grpc_java_api",
        "//third_party:grpc_java_stub",
        "//third_party:jenetics",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
    ],
)

# If you wish to build a service runner, you might do a java_binary or container image:
java_binary(
    name = "ga_service_bin",
    srcs = [],
    main_class = "com.verlumen.tradestream.ga.GAServiceMain",  # if you define one
    deps = [":ga_service_module"],
)

# (Optional) Containerization
oci_image(
    name = "ga_service_image",
    base = "@openjdk_java",
    tars = [":ga_service_bin_deploy.jar"],
    entrypoint = [
        "java",
        "-jar",
        "/src/main/java/com/verlumen/tradestream/ga/ga_service_bin_deploy.jar",
    ],
)

container_structure_test(
    name = "ga_service_image_test",
    image = ":ga_service_image",
    configs = ["container-structure-test.yaml"],
    tags = ["requires-docker"],
)

oci_push(
    name = "push_ga_service_image",
    image = ":ga_service_image",
    repository = "tradestreamhq/tradestream-ga-service",
    remote_tags = ["latest"],
)
