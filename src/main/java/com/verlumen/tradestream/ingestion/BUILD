load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_java//java:defs.bzl", "java_binary", "java_library", "java_test")
load("@rules_oci//oci:defs.bzl", "oci_image")

package(default_visibility = ["//visibility:public"])

java_binary(
    name = "java-maven",
    srcs
    main_class = "com.verlumen.tradestream.ingestion.RealTimeDataIngestion",
    deps = ["@maven//:com_google_guava_guava"],
)

tar(
    name = "layer",
    srcs = ["java-maven_deploy.jar"],
)

oci_image(
    name = "image",
    base = "@distroless_java",
    entrypoint = [
        "java",
        "-jar",
        "/java-maven-deploy.jar",
    ],
    tars = [":layer"],
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
