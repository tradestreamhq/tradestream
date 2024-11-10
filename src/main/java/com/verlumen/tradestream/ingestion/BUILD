load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("//platforms:transition.bzl", "multi_arch")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "app-lib",
    srcs = ["App.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
        ":ingestion_module",
        ":market-data-ingestion",
        ":real-time-data-ingestion",
    ],
)

java_binary(
    name = "app",
    main_class = "com.verlumen.tradestream.ingestion.App",
    runtime_deps = [":app-lib"],
)

java_library(
    name = "candle-key",
    srcs = ["CandleKey.java"],
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)

# Base image target
oci_image(
    name = "image",
    base = "@distroless_java",
    cmd = [
        "java",
        "-jar",
        "/src/main/java/com/verlumen/tradestream/ingestion/app_deploy.jar",
    ],
    tars = [":layer"],
)

# Multi-arch index
oci_image_index(
    name = "index",
    images = select({
        "@platforms//cpu:arm64": {
            "linux/arm64": ":image",
        },
        "@platforms//cpu:x86_64": {
            "linux/amd64": ":image",
        },
        "//conditions:default": {
            "linux/amd64": ":image",
        },
    }),
)

java_library(
    name = "ingestion_module",
    srcs = ["IngestionModule.java"],
    deps = [
        "@maven//:com_google_inject_guice",
        ":market-data-ingestion",
        ":real-time-data-ingestion",
    ],
)

tar(
    name = "layer",
    srcs = [":app_deploy.jar"],
)

java_library(
    name = "market-data-ingestion",
    srcs = ["MarketDataIngestion.java"],
)

oci_push(
    name = "push_image",
    image = ":index",
    remote_tags = ["latest"],
    repository = "tradestreamhq/tradestream-data-ingestion",
)

java_library(
    name = "real-time-data-ingestion",
    srcs = ["RealTimeDataIngestion.java"],
    deps = [
        "@maven//:com_google_inject_guice",
        ":market-data-ingestion",
    ]
)
