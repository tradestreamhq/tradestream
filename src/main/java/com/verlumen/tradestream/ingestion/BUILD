load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("@rules_oci//oci:defs.bzl", "oci_image")

package(default_visibility = ["//visibility:public"])

java_binary(
    name = "realtime-data-ingestion",
    srcs = ["RealtimeDataIngestion.java"],
    main_class = "com.verlumen.tradestream.ingestion.RealTimeDataIngestion",
    deps = ["@maven//:com_google_guava_guava"],
)

tar(
    name = "layer",
    srcs = ["realtime-data-ingestion_deploy.jar"],
)

oci_image(
    name = "image",
    base = "@distroless_java",
    entrypoint = [
        "java",
        "-jar",
        "/realtime-data-ingestion-deploy.jar",
    ],
    tars = [":layer"],
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
