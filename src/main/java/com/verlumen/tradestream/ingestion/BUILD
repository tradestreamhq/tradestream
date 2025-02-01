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
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
        "//third_party:argparse4j",
        "//third_party:flogger",
        "//third_party:guice",
        ":ingestion_config",
        ":ingestion_module",
        ":real_time_data_ingestion",
        ":real_time_data_ingestion_impl",
    ],
)

java_library(
    name = "candle_builder",
    srcs = ["CandleBuilder.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:flogger",
        "//third_party:protobuf_java",
        "//third_party:protobuf_java_util",
    ],
)

java_library(
    name = "candle_manager",
    srcs = ["CandleManager.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        ":candle_publisher",
    ],
)

java_library(
    name = "candle_manager_impl",
    srcs = ["CandleManagerImpl.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:auto_value",
        "//third_party:flogger",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:protobuf_java_util",
        ":candle_builder",
        ":candle_manager",
        ":candle_publisher",
        ":price_tracker",
    ],
)

java_library(
    name = "candle_publisher",
    srcs = ["CandlePublisher.java"],
    deps = [
        "//protos:marketdata_java_proto",
    ],
)

java_library(
    name = "candle_publisher_impl",
    srcs = ["CandlePublisherImpl.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:flogger",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:kafka_clients",
        "//third_party:protobuf_java_util",
        ":candle_publisher",
    ],
)

java_library(
    name = "coinbase_streaming_client",
    srcs = ["CoinbaseStreamingClient.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:flogger",
        "//third_party:gson",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:protobuf_java_util",
        ":exchange_streaming_client",
    ],
)

java_library(
    name = "coin_market_cap_config",
    srcs = ["CoinMarketCapConfig.java"],
    deps = [
        "//third_party:auto_value",
    ],
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)

java_library(
    name = "currency_pair_metadata",
    srcs = ["CurrencyPairMetadata.java"],
    deps = [
        "//third_party:auto_value",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
    ],
)

java_library(
    name = "currency_pair_supply",
    srcs = ["CurrencyPairSupply.java"],
    deps = [
        "//third_party:guava",
        "//third_party:auto_value",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        ":currency_pair_metadata",
    ],
)

java_library(
    name = "currency_pair_supply_provider",
    srcs = ["CurrencyPairSupplyProvider.java"],
    deps = [
        "//third_party:gson",
        "//third_party:guava",
        "//third_party:guice",
        ":coin_market_cap_config",
        ":currency_pair_metadata",
        ":currency_pair_supply",
        "//src/main/java/com/verlumen/tradestream/http:http_client",
    ],
)

java_library(
    name = "exchange_streaming_client",
    srcs = ["ExchangeStreamingClient.java"],
    deps = [
        "//third_party:guava",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
    ],
)

java_library(
    name = "exchange_streaming_client_factory",
    srcs = ["ExchangeStreamingClientFactory.java"],
    deps = [
        "//third_party:guava",
        "//third_party:guice",
        ":coinbase_streaming_client",
        ":exchange_streaming_client",
    ],
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
        ":candle_manager",
        ":candle_manager_impl",
        ":candle_publisher",
        ":candle_publisher_impl",
        ":coin_market_cap_config",
        ":currency_pair_supply",
        ":currency_pair_supply_provider",
        ":exchange_streaming_client",
        ":exchange_streaming_client_factory",
        ":ingestion_config",
        ":real_time_data_ingestion",
        ":real_time_data_ingestion_impl",
        ":thin_market_timer",
        ":thin_market_timer_impl",
        ":thin_market_timer_task",
        ":thin_market_timer_task_impl",
        ":trade_processor",
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
        "//src/main/java/com/verlumen/tradestream/http:http_module",
        "//src/main/java/com/verlumen/tradestream/kafka:kafka_module",
        "//src/main/java/com/verlumen/tradestream/marketdata:market_data_config",
        "//src/main/java/com/verlumen/tradestream/marketdata:market_data_module",
        "//third_party:auto_value",
        "//third_party:guava",
        "//third_party:guice_assistedinject",
        "//third_party:guice",
    ],
)

tar(
    name = "layer",
    srcs = [":app_deploy.jar"],
)

java_library(
    name = "price_tracker",
    srcs = ["PriceTracker.java"],
    deps = [
        "//third_party:guice",        
    ],
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
        ":candle_manager",
        ":candle_publisher",
        ":currency_pair_supply",
        ":exchange_streaming_client",
        ":real_time_data_ingestion",
        ":thin_market_timer",
        ":trade_processor",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//src/main/java/com/verlumen/tradestream/marketdata:trade_publisher",
        "//third_party:flogger",
        "//third_party:guava",
        "//third_party:guice",
    ],
)

java_library(
    name = "thin_market_timer",
    srcs = ["ThinMarketTimer.java"],
)

java_library(
    name = "thin_market_timer_impl",
    srcs = ["ThinMarketTimerImpl.java"],
    deps = [
        ":thin_market_timer",
        ":thin_market_timer_task",
        "//third_party:flogger",
        "//third_party:guice",
        "//third_party:xchange_core",
    ],
)

java_library(
    name = "thin_market_timer_task",
    srcs = ["ThinMarketTimerTask.java"],
)

java_library(
    name = "thin_market_timer_task_impl",
    srcs = ["ThinMarketTimerTaskImpl.java"],
    deps = [
        ":candle_manager",
        ":currency_pair_supply",
        ":thin_market_timer_task",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:guava",
        "//third_party:guice",
    ],
)

java_library(
    name = "trade_processor",
    srcs = ["TradeProcessor.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party:auto_value",
        "//third_party:flogger",
        "//third_party:protobuf_java_util",
    ],
)
