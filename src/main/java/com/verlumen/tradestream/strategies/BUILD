load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_java//java:defs.bzl", "java_binary", "java_library")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("//platforms:transition.bzl", "multi_arch")

package(default_visibility = ["//visibility:public"])

java_binary(
    name = "app",
    srcs = ["App.java"],
    main_class = "com.verlumen.tradestream.strategies.App",
    deps = [
        "//third_party:flogger",
        "//third_party:guice",
    ],
    runtime_deps = [
        "//third_party:flogger_system_backend",
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
        "/src/main/java/com/verlumen/tradestream/strategies/app_deploy.jar",
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

oci_push(
    name = "push_image",
    image = ":index",
    remote_tags = ["latest"],
    repository = "tradestreamhq/tradestream-strategy-engine",
)

java_library(
    name = "strategy_engine",
    srcs = [
        "StrategyEngine.java",
        "StrategyEngineImpl.java",        
    ],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "strategy_factory",
    srcs = ["StrategyFactory.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "strategy_manager",
    srcs = ["StrategyManager.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
        ":strategy_factory",
    ],
)

java_library(
    name = "strategy_manager_impl",
    srcs = ["StrategyManagerImpl.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party:auto_value",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:mug",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
        ":strategy_factory",
        ":strategy_manager",
    ],
)
