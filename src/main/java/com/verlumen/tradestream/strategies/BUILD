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
        "//src/main/java/com/verlumen/tradestream/execution:execution_module",
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_module",
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_properties",
        "//third_party:argparse4j",
        "//third_party:flogger",
        "//third_party:guice",
        ":market_data_consumer",
        ":strategies_module",
        ":strategy_engine",
    ],
    runtime_deps = [
        "//third_party:flogger_system_backend",
    ],
)

java_library(
    name = "candle_buffer",
    srcs = ["CandleBuffer.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:guava",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "candle_buffer_impl",
    srcs = ["CandleBufferImpl.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:guava",
        "//third_party:protobuf_java_util",
        "//third_party:ta4j_core",
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

java_library(
    name = "market_data_consumer",
    srcs = ["MarketDataConsumer.java"],
    deps = [
        "//protos:marketdata_java_proto",
    ],
)

java_library(
    name = "market_data_consumer_impl",
    srcs = ["MarketDataConsumerImpl.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:guice",
        ":market_data_consumer",
    ],
)

oci_push(
    name = "push_image",
    image = ":index",
    remote_tags = ["latest"],
    repository = "tradestreamhq/tradestream-strategy-engine",
)

java_library(
    name = "strategies_module",
    srcs = ["StrategiesModule.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/backtesting:backtesting_module",
        "//src/main/java/com/verlumen/tradestream/signals:signals_module",
        "//src/main/java/com/verlumen/tradestream/signals:trade_signal_publisher",
        "//third_party:auto_value",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        ":candle_buffer",
        ":candle_buffer_impl",
        ":market_data_consumer",
        ":market_data_consumer_impl",
        ":strategy_engine",
        ":strategy_engine_impl",
        ":strategy_factories",
        ":strategy_factory",
        ":strategy_manager",
        ":strategy_manager_impl",
    ],
)

java_library(
    name = "strategy_engine",
    srcs = ["StrategyEngine.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:ta4j_core",
    ],
)

java_library(
    name = "strategy_engine_impl",
    srcs = ["StrategyEngineImpl.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//protos:trade_signals_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:ga_service_client",
        "//src/main/java/com/verlumen/tradestream/signals:trade_signal_publisher",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
        ":candle_buffer",
        ":strategy_engine",
        ":strategy_manager",
    ],
)

java_library(
    name = "strategy_factories",
    srcs = ["StrategyFactories.java"],
    deps = [
        ":strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies/movingaverages:movingaverages_lib",
        "//src/main/java/com/verlumen/tradestream/strategies/oscillators:oscillators_lib",
        "//third_party:guava",
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
        "//third_party:guava",
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
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:mug",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
        ":strategy_factory",
        ":strategy_manager",
    ],
)
