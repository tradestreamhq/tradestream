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
    name = "candle-key",
    srcs = ["CandleKey.java"],
)

# Create separate images for each architecture
oci_image(
    name = "image_amd64",
    base = "@distroless_java",
    entrypoint = [
        "java",
        "-jar",
        "/src/main/java/com/verlumen/tradestream/ingestion/app_deploy.jar",
    ],
    tars = [":layer"],
    architecture = "amd64",
    os = "linux",
)

oci_image(
    name = "image_arm64",
    base = "@distroless_java",
    entrypoint = [
        "java",
        "-jar",
        "/src/main/java/com/verlumen/tradestream/ingestion/app_deploy.jar",
    ],
    tars = [":layer"],
    architecture = "arm64",
    os = "linux",
)

# Create an image index that includes both architectures
oci_image_index(
    name = "multi_arch_image",
    images = [
        ":image_amd64",
        ":image_arm64",
    ],
)

# Single push rule for the multi-arch image
oci_push(
    name = "push_image",
    image = ":multi_arch_image",
    repository = "tradestreamhq/tradestream-data-ingestion",
)

# Test rules
container_structure_test(
    name = "container_test_amd64",
    configs = ["container-structure-test.yaml"],
    image = ":image_amd64",
    tags = ["requires-docker"],
)

container_structure_test(
    name = "container_test_arm64",
    configs = ["container-structure-test.yaml"],
    image = ":image_arm64",
    tags = ["requires-docker"],
)

test_suite(
    name = "container_test",
    tests = [
        ":container_test_amd64",
        ":container_test_arm64",
    ],
)

tar(
    name = "layer",
    srcs = [":app_deploy.jar"],
)

genrule(
    name = "hash",
    srcs = [":multi_arch_image"],
    outs = ["sha256.sum"],
    cmd = "$(JQ_BIN) -r '.manifests[0].digest' $(location :multi_arch_image)/index.json > $@",
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

java_library(
    name = "market-data-ingestion",
    srcs = ["MarketDataIngestion.java"],
)

java_library(
    name = "real-time-data-ingestion",
    srcs = ["RealTimeDataIngestion.java"],
    deps = [
        "@maven//:com_google_inject_guice",
        ":market-data-ingestion",
    ]
)
