load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("//platforms:transition.bzl", "multi_arch")

package(default_visibility = ["//visibility:public"])

java_binary(
    name = "app",
    srcs = ["App.java"],
    main_class = "com.verlumen.tradestream.ingestion.App",
    deps = [
        ":ingestion_config",
        ":ingestion_module",
        ":real_time_data_ingestion",
        ":real_time_data_ingestion_impl",
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
        "//third_party:argparse4j",
        "//third_party:flogger",
        "//third_party:guice",
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
    base = "@openjdk_java",
    entrypoint = [
        "java",
        "-jar",
        "/src/main/java/com/verlumen/tradestream/ingestion/app_deploy.jar",
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

java_library(
    name = "ingestion_config",
    srcs = ["IngestionConfig.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
    ],
)

java_library(
    name = "ingestion_module",
    srcs = ["IngestionModule.java"],
    deps = [
        ":ingestion_config",
        ":real_time_data_ingestion",
        ":real_time_data_ingestion_impl",
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
        "//src/main/java/com/verlumen/tradestream/instruments:coin_market_cap_config",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair_supply",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair_supply_provider",
        "//src/main/java/com/verlumen/tradestream/http:http_module",
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_module",
        "//src/main/java/com/verlumen/tradestream/marketdata:market_data_module",
        "//third_party:auto_value",
        "//third_party:guava",
        "//third_party:guice",
    ],
)

tar(
    name = "layer",
    srcs = [":app_deploy.jar"],
)

oci_push(
    name = "push_image",
    image = ":index",
    remote_tags = ["latest"],
    repository = "tradestreamhq/tradestream-data-ingestion",
)

java_library(
    name = "real_time_data_ingestion",
    srcs = ["RealTimeDataIngestion.java"],
)

java_library(
    name = "real_time_data_ingestion_impl",
    srcs = ["RealTimeDataIngestionImpl.java"],
    deps = [
        ":real_time_data_ingestion",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair_supply",
        "//src/main/java/com/verlumen/tradestream/marketdata:exchange_streaming_client",
        "//src/main/java/com/verlumen/tradestream/marketdata:trade_publisher",
        "//third_party:flogger",
        "//third_party:guava",
        "//third_party:guice",
    ],
)
