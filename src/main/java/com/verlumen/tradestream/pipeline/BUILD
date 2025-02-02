load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("//platforms:transition.bzl", "multi_arch")

package(default_visibility = ["//visibility:public"])

java_binary(
  name = "app",
  main_class = "com.verlumen.tradestream.pipeline.App",
  srcs = ["App.java"],
  deps = [
    ":pipeline_module",
    "//protos:marketdata_java_proto",
    "//src/main/java/com/verlumen/tradestream/kafka:kafka_read_transform",
    "//src/main/java/com/verlumen/tradestream/marketdata:create_candles",
    "//src/main/java/com/verlumen/tradestream/marketdata:parse_trades",
    "//third_party:beam_runners_flink_java",
    "//third_party:beam_sdks_java_core",
    "//third_party:guice",
    "//third_party:protobuf_java",
  ],
  runtime_deps = [
    "//third_party:beam_runners_direct_java",
  ],
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)

genrule(
    name = "hash",
    srcs = [":index"],
    outs = ["sha256.sum"],
    cmd = "$(JQ_BIN) -r '.manifests[0].digest' $(location :index)/index.json > $@",
    toolchains = ["@jq_toolchains//:resolved_toolchain"],
)

oci_image(
    name = "image",
    base = "@flink_java17",
    entrypoint = [
        "java",
        "-jar",
        "/src/main/java/com/verlumen/tradestream/pipeline/app_deploy.jar",
    ],
    tars = [":layer"],
)

multi_arch(
    name = "images",
    image = ":image",
    platforms = [
        "//platforms:linux_arm64",
        "//platforms:linux_amd64",
    ],
)

oci_image_index(
    name = "index",
    images = [
        ":images",
    ],
)

tar(
    name = "layer",
    srcs = [":app_deploy.jar"],
)

java_library(
    name = "pipeline_module",
    srcs = ["PipelineModule.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/execution:execution_module",
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
        "//src/main/java/com/verlumen/tradestream/kafka:dry_run_kafka_read_transform",
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_module",
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_read_transform",
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_read_transform_factory",
        "//third_party:auto_value",
        "//third_party:guice",
        "//third_party:kafka_clients",
        "//third_party:protobuf_java_util",
    ],
)

oci_push(
    name = "push_image",
    image = ":index",
    remote_tags = ["latest"],
    repository = "tradestreamhq/tradestream-data-pipeline",
)
