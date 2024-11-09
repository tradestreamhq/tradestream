load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("@rules_oci//oci:defs.bzl", "oci_image")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "candle-key",
    srcs = ["CandleKey.java"]
)

java_binary(
    name = "real-time-data-ingestion",
    srcs = ["RealTimeDataIngestion.java"],
    main_class = "com.verlumen.tradestream.ingestion.RealTimeDataIngestion",
    deps = [
        "@maven//:org_knowm_xchange_xchange_coinbasepro",
        "@maven//:org_knowm_xchange_xchange_core",
        "@maven//:org_knowm_xchange_xchange_stream_core",
        "@maven//:org_knowm_xchange_xchange_stream_coinbasepro",
        "@maven//:io_reactivex_rxjava3_rxjava",
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_protobuf_protobuf_java",
        "@maven//:org_apache_kafka_kafka_clients",
        "@maven//:org_slf4j_slf4j_api",
        "//protos:marketdata_java_proto",
        ":candle-key",
    ],
)

tar(
    name = "layer",
    srcs = [
        "real-time-data-ingestion_deploy.jar",
    ],
)

oci_image(
    name = "image",
    base = "@distroless_java",
    entrypoint = [
        "java",
        "-jar",
        "/real-time-data-ingestion-deploy.jar",
    ],
    tars = [":layer"],
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
