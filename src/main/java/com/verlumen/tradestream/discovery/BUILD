load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_binary", "kt_jvm_library")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("//platforms:transition.bzl", "multi_arch")  # If multi-arch is needed

package(default_visibility = ["//visibility:public"])

kt_jvm_library(
    name = "strategy_discovery_pipeline_lib",
    srcs = [
        "StrategyDiscoveryPipeline.kt",
        "StrategyDiscoveryPipelineOptions.kt",
    ],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:discovery_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:ga_engine_factory",
        "//src/main/java/com/verlumen/tradestream/backtesting:genotype_converter",
        "//src/main/java/com/verlumen/tradestream/marketdata:influxdb_candle_fetcher",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_io_kafka",
        "//third_party/java:beam_sdks_java_io_jdbc",
        "//third_party/java:beam_sdks_java_io_kafka",
        "//third_party/java:flogger",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:kafka_clients",
        "//third_party/java:postgresql_jdbc",  # Your DB driver, e.g. org.postgresql:postgresql
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:guava",
        "//third_party/java:flogger",
        "//third_party/java:jenetics",
        "//third_party/java:postgresql_jdbc", # Your DB driver, e.g. org.postgresql:postgresql
        "//third_party/kotlin:kotlin_stdlib",
    ],
)

kt_jvm_binary(
    name = "strategy_discovery_app",
    main_class = "com.verlumen.tradestream.discovery.StrategyDiscoveryPipeline",  # Ensure correct if main is in object
    runtime_deps = [
        ":strategy_discovery_pipeline_lib",
        "//third_party/java:beam_runners_direct_java",  # For local testing
        "//third_party/java:beam_runners_flink_java",  # For Flink execution
        # Add other runtime dependencies for Flink cluster execution if needed (e.g., specific connectors)
    ],
)

tar(
    name = "discovery_layer",
    srcs = [":strategy_discovery_app_deploy.jar"], # Assumes the _deploy.jar convention
)

oci_image(
    name = "discovery_image",
    base = "@flink_java17//image", # Reference the image from the oci_pull rule in MODULE.bazel [cite: 1234]
    entrypoint = [
        "/opt/flink/bin/flink-console.sh", # Standard Flink entrypoint
    ],
    # cmd is usually set by FlinkDeployment in Kubernetes to run the specific job.
    # Example: ["run", "-c", "com.verlumen.tradestream.discovery.StrategyDiscoveryPipeline", "/app/strategy_discovery_app_deploy.jar", "--runner=FlinkRunner", ...]
    # For this image, we just package the jar. The actual run command will be in the FlinkDeployment.
    tars = [":discovery_layer"],
    workdir = "/opt/flink", # Standard Flink workdir
    # Ensure the JAR is placed where Flink can find it, e.g., /opt/flink/usrlib or /app
    # The tar rule by default places files at the root.
    # Adjust entrypoint/jarURI in FlinkDeployment or path here if needed.
    # This example assumes the JAR is in /app within the image.
    # If :discovery_layer places it at root, then /strategy_discovery_app_deploy.jar
)

# If multi-arch: (Uncomment and adjust if needed)
# multi_arch(
#     name = "discovery_images_multiarch",
#     image = ":discovery_image",
#     platforms = [
#         "//platforms:linux_arm64",
#         "//platforms:linux_amd64",
#     ],
# )
# oci_image_index(
#     name = "discovery_index",
#     images = [":discovery_images_multiarch"],
# )

oci_push(
    name = "push_discovery_image",
    # image = ":discovery_index", # if multi-arch
    image = ":discovery_image", # if single-arch
    repository = "tradestreamhq/tradestream-strategy-discovery", # New Docker Hub repo
    # remote_tags will be set by release.yaml
)
