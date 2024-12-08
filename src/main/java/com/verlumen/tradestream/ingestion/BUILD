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
        "@maven//:com_google_flogger_flogger",
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
        ":ingestion_module",
        ":real_time_data_ingestion",
        ":real_time_data_ingestion_impl",
        ":run_mode",
    ],
    runtime_deps = [
        "@maven//:com_google_flogger_flogger_system_backend",
    ],
)

java_library(
    name = "candle_builder",
    srcs = ["CandleBuilder.java"],
    deps = [
        "@maven//:com_google_flogger_flogger",
        "//protos:marketdata_java_proto",
    ],
    runtime_deps = [
        "@maven//:com_google_flogger_flogger_system_backend",
    ],
)

java_library(
    name = "candle_manager",
    srcs = ["CandleManager.java"],
    deps = [
        "//protos:marketdata_java_proto",
        ":candle_publisher",
    ],
)

java_library(
    name = "candle_manager_impl",
    srcs = ["CandleManagerImpl.java"],
    deps = [
        "@maven//:com_google_flogger_flogger",
        "@maven//:com_google_inject_extensions_guice_assistedinject",
        "@maven//:com_google_inject_guice",
        "//protos:marketdata_java_proto",
        ":candle_builder",
        ":candle_manager",
        ":candle_publisher",
        ":price_tracker",
    ],
    runtime_deps = [
        "@maven//:com_google_flogger_flogger_system_backend",
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
        "@maven//:com_google_flogger_flogger",
        "@maven//:com_google_inject_extensions_guice_assistedinject",
        "@maven//:com_google_inject_guice",
        "@maven//:org_apache_kafka_kafka_clients",
        "//protos:marketdata_java_proto",
        ":candle_publisher",
    ],
    runtime_deps = [
        "@maven//:com_google_flogger_flogger_system_backend",
    ],
)

java_library(
    name = "coinbase_streaming_client",
    srcs = ["CoinbaseStreamingClient.java"],
    deps = [
        "@maven//:com_google_flogger_flogger",
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
        "@maven//:com_google_code_gson_gson",
        "//protos:marketdata_java_proto",
        ":exchange_streaming_client",
    ],
    runtime_deps = [
        "@maven//:com_google_flogger_flogger_system_backend",
    ],
)

java_library(
    name = "coin_market_cap_config",
    srcs = ["CoinMarketCapConfig.java"],
    deps = [
        "//:autovalue",
    ],
)

java_library(
    name = "config_arguments",
    srcs = ["ConfigArguments.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
        "@maven//:net_sourceforge_argparse4j_argparse4j",
        "//:autovalue",
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
        "//:autovalue",
        "//src/main/java/com/verlumen/tradestream/instruments:currency",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
    ],
)

java_library(
    name = "currency_pair_supply",
    srcs = ["CurrencyPairSupply.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        ":currency_pair_metadata",
    ],
)

java_library(
    name = "currency_pair_supply_impl",
    srcs = ["CurrencyPairSupplyImpl.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "//:autovalue",
        ":currency_pair_metadata",
        ":currency_pair_supply",
    ],
)

java_library(
    name = "currency_pair_supply_provider",
    srcs = ["CurrencyPairSupplyProvider.java"],
    deps = [
        "@maven//:com_google_code_gson_gson",
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
        ":coin_market_cap_config",
        ":currency_pair_metadata",
        ":currency_pair_supply",
        ":currency_pair_supply_impl",
        ":http_client",
    ],
)

java_library(
    name = "exchange_streaming_client",
    srcs = ["ExchangeStreamingClient.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
    ],
)

java_library(
    name = "exchange_streaming_client_factory",
    srcs = ["ExchangeStreamingClientFactory.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
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

java_library(
    name = "http_client",
    srcs = ["HttpClient.java"],
)

java_library(
    name = "http_client_impl",
    srcs = ["HttpClientImpl.java"],
    deps = [
        "@maven//:com_google_flogger_flogger",
        "@maven//:com_google_inject_guice",
        ":http_client",
        ":http_url_connection_factory",
    ],
    runtime_deps = [
        "@maven//:com_google_flogger_flogger_system_backend",
    ],
)

java_library(
    name = "http_url_connection_factory",
    srcs = ["HttpURLConnectionFactory.java"],
)

java_library(
    name = "http_url_connection_factory_impl",
    srcs = ["HttpURLConnectionFactoryImpl.java"],
    deps = [
        "@maven//:com_google_inject_guice",
        ":http_url_connection_factory",
    ],
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
    name = "ingestion_module",
    srcs = ["IngestionModule.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_extensions_guice_assistedinject",
        "@maven//:com_google_inject_guice",
        "@maven//:net_sourceforge_argparse4j_argparse4j",
        "@maven//:org_apache_kafka_kafka_clients",
        "@maven//:org_knowm_xchange_xchange_stream_core",
        "//:autovalue",
        ":candle_manager",
        ":candle_manager_impl",
        ":candle_publisher",
        ":candle_publisher_impl",
        ":coin_market_cap_config",
        ":config_arguments",
        ":currency_pair_supply",
        ":currency_pair_supply_provider",
        ":exchange_streaming_client",
        ":exchange_streaming_client_factory",
        ":http_client",
        ":http_client_impl",
        ":http_url_connection_factory",
        ":http_url_connection_factory_impl",
        ":kafka_producer_provider",
        ":real_time_data_ingestion",
        ":real_time_data_ingestion_impl",
        ":run_mode",
        ":thin_market_timer",
        ":thin_market_timer_impl",
        ":thin_market_timer_task",
        ":thin_market_timer_task_impl",
        ":trade_processor",
    ],
)

java_library(
    name = "kafka_producer_provider",
    srcs = ["KafkaProducerProvider.java"],
    deps = [
        "@maven//:com_google_inject_guice",
        "@maven//:org_apache_kafka_kafka_clients",
        ":kafka_properties",
    ],    
)

java_library(
    name = "kafka_properties",
    srcs = ["KafkaProperties.java"],
    deps = [
        "@maven//:com_google_inject_guice",
        "@maven//:net_sourceforge_argparse4j_argparse4j",
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
    name = "real_time_data_ingestion",
    srcs = ["RealTimeDataIngestion.java"],
)

java_library(
    name = "real_time_data_ingestion_impl",
    srcs = ["RealTimeDataIngestionImpl.java"],
    deps = [
        "@maven//:com_google_flogger_flogger",
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
        "//protos:marketdata_java_proto",
        ":candle_manager",
        ":candle_publisher",
        ":currency_pair_supply",
        ":exchange_streaming_client",
        ":real_time_data_ingestion",
        ":thin_market_timer",
        ":trade_processor",
    ],
    runtime_deps = [
        "@maven//:com_google_flogger_flogger_system_backend",
    ],
)

java_library(
    name = "run_mode",
    srcs = ["RunMode.java"],
)

java_library(
    name = "thin_market_timer",
    srcs = ["ThinMarketTimer.java"],
)

java_library(
    name = "thin_market_timer_impl",
    srcs = ["ThinMarketTimerImpl.java"],
    deps = [
        "@maven//:com_google_flogger_flogger",
        "@maven//:com_google_inject_guice",
        "@maven//:org_knowm_xchange_xchange_core",
        ":thin_market_timer",
        ":thin_market_timer_task",
    ],
    runtime_deps = [
        "@maven//:com_google_flogger_flogger_system_backend",
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
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
        ":candle_manager",
        ":currency_pair_supply",
        ":thin_market_timer_task",
    ],
)

java_library(
    name = "trade_processor",
    srcs = ["TradeProcessor.java"],
    deps = [
        "@maven//:com_google_flogger_flogger",
        "//:autovalue",
        "//protos:marketdata_java_proto",
    ],
    runtime_deps = [
        "@maven//:com_google_flogger_flogger_system_backend",
    ],
)
