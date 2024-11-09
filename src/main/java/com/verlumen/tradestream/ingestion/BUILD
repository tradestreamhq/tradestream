load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("@rules_oci//oci:defs.bzl", "oci_image")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "candle-key",
    srcs = ["CandleKey.java"],
)

java_library(
    name = "real-time-data-ingestion-lib",
    srcs = ["RealTimeDataIngestion.java"],
    deps = [
        "@maven//:com_google_inject_guice",
    ]
)

java_binary(
    name = "real-time-data-ingestion",
    main_class = "com.verlumen.tradestream.RealTimeDataIngestion",
    runtime_deps = [":real-time-data-ingestion-lib"],
)

java_library(
    name = "app-lib",
    srcs = ["App.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
    ],
)

java_binary(
    name = "app",
    main_class = "com.example.myproject.App",
    runtime_deps = [":app-lib"],
)

tar(
    name = "layer",
    srcs = [":app_deploy.jar"],
)

oci_image(
    name = "image",
    base = "@distroless_java",
    entrypoint = [
        "java",
        "-jar",
        "/src/main/java/com/verlumen/tradestream/ingestion/app_deploy.jar",
    ],
    tars = [":layer"],
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
