load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("//platforms:transition.bzl", "multi_arch")

package(default_visibility = ["//visibility:public"])

java_binary(
    name = "app",
    srcs = ["App.java"],
    jvm_flags = [
        "-Dio.jenetics.util.defaultRandomGenerator=Random",
    ],
    main_class = "com.verlumen.tradestream.pipeline.App",
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
    ],
    deps = [
        ":pipeline_module",
        ":timing_config",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
        "//src/main/java/com/verlumen/tradestream/influxdb:influx_db_module",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_lookback_do_fn",
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_source",
        "//third_party/java:beam_runners_flink_java",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:flogger",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:joda_time",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
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
    tars = [
        ":layer",
    ],
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
        ":timing_config",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtesting_module",
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
        "//src/main/java/com/verlumen/tradestream/http:http_module",
        "//src/main/java/com/verlumen/tradestream/instruments:instruments_module",
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_module",
        "//src/main/java/com/verlumen/tradestream/marketdata:fill_forward_candles",
        "//src/main/java/com/verlumen/tradestream/marketdata:market_data_module",
        "//src/main/java/com/verlumen/tradestream/marketdata:trade_to_candle",
        "//src/main/java/com/verlumen/tradestream/signals:signals_module",
        "//src/main/java/com/verlumen/tradestream/strategies:strategies_module",
        "//src/main/java/com/verlumen/tradestream/ta4j:ta4j_module",
        "//third_party/java:auto_value",
        "//third_party/java:guice",
        "//third_party/java:joda_time",
        "//third_party/java:protobuf_java_util",
    ],
)

oci_push(
    name = "push_image",
    image = ":index",
    remote_tags = ["latest"],
    repository = "tradestreamhq/tradestream-data-pipeline",
)

java_library(
    name = "timing_config",
    srcs = ["TimingConfig.java"],
    deps = [
        "//third_party/java:joda_time",
    ],
)
