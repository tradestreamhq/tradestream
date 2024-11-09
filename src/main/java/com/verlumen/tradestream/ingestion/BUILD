load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("@rules_oci//oci:defs.bzl", "oci_image")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "candle-key",
    srcs = ["CandleKey.java"]
)

java_library(
    name = "real-time-data-ingestion",
    srcs = ["RealTimeDataIngestion.java"],
    deps = [
        "@maven//:org_knowm_xchange_xchange_coinbasepro",
        "@maven//:org_knowm_xchange_xchange_core",
        "@maven//:org_knowm_xchange_xchange_stream_core",
        "@maven//:org_knowm_xchange_xchange_stream_coinbasepro",
        "@maven//:io_reactivex_rxjava3_rxjava",
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
        "@maven//:com_google_protobuf_protobuf_java",
        "@maven//:org_apache_kafka_kafka_clients",
        "@maven//:org_slf4j_slf4j_api",
        "//protos:marketdata_java_proto",
        ":candle-key",
    ],
)

java_library(
    name = "java-maven-lib",
    srcs = ["App.java"],
    deps = ["@maven//:com_google_guava_guava"],
)

java_binary(
    name = "java-maven",
    main_class = "com.example.myproject.App",
    runtime_deps = [":java-maven-lib"],
)

tar(
    name = "layer",
    srcs = [":java-maven_deploy.jar"],
)

oci_image(
    name = "image",
    base = "@distroless_java",
    entrypoint = [
        "java",
        "-jar",
        "/src/main/java/com/verlumen/tradestream/ingestion/java-maven_deploy.jar",
    ],
    tars = [":layer"],
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
