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
    name = "candle-builder",
    srcs = ["CandleBuilder.java"],
    deps = [
        "//protos:marketdata_java_proto",
    ],
)

java_library(
    name = "candle-key",
    srcs = ["CandleKey.java"],
)

java_library(
    name = "candle-manager",
    srcs = ["CandleManager.java"],
    deps = [
        ":candle-builder",
        ":candle_publisher_impl",
        ":price-tracker",
        "//protos:marketdata_java_proto",
    ],
)

java_library(
    name = "candle_publisher_impl",
    srcs = ["CandlePublisherImpl.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "@maven//:org_apache_kafka_kafka_clients",
    ],
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
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

genrule(
    name = "hash",
    srcs = [":index"],
    outs = ["sha256.sum"],
    cmd = "$(JQ_BIN) -r '.manifests[0].digest' $(location :index)/index.json > $@",
    toolchains = ["@jq_toolchains//:resolved_toolchain"],
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

java_library(
    name = "price-tracker",
    srcs = ["PriceTracker.java"],
    deps = [
        "@maven//:com_google_inject_guice",        
    ],
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

java_library(
    name = "trade-processor",
    srcs = ["TradeProcessor.java"],
    deps = [
        ":candle-key",
        "//protos:marketdata_java_proto",
    ],
    visibility = ["//visibility:public"],
)
