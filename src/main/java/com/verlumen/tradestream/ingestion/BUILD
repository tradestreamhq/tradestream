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
        ":market_data_ingestion",
        ":real_time_data_ingestion",
        ":run_mode",
        ":streaming_exchange_provider",
    ],
    runtime_deps = [
        "@maven//:com_google_flogger_flogger_system_backend",
    ],
)

java_library(
    name = "candle_builder",
    srcs = ["CandleBuilder.java"],
    deps = [
        "//protos:marketdata_java_proto",
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
        "@maven//:com_google_inject_extensions_guice_assistedinject",
        "@maven//:com_google_inject_guice",
        "//protos:marketdata_java_proto",
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
        "@maven//:com_google_inject_extensions_guice_assistedinject",
        "@maven//:com_google_inject_guice",
        "@maven//:org_apache_kafka_kafka_clients",
        "//protos:marketdata_java_proto",
        ":candle_publisher",
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
        "@maven//:org_knowm_xchange_xchange_core",
        "//:autovalue",
    ],
)

java_library(
    name = "currency_pair_supplier",
    srcs = ["CurrencyPairSupplier.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "@maven//:org_knowm_xchange_xchange_core",
        ":currency_pair_metadata",
    ],
)

java_library(
    name = "currency_pair_supplier_impl",
    srcs = ["CurrencyPairSupplierImpl.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        ":currency_pair_metadata",
        ":currency_pair_supplier",
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
        ":config_arguments",
        ":currency_pair_supplier",
        ":currency_pair_supplier_impl",
        ":kafka_producer_provider",
        ":market_data_ingestion",
        ":real_time_data_ingestion",
        ":run_mode",
        ":streaming_exchange_provider",
        ":thin_market_timer",
        ":thin_market_timer_impl",
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
    name = "market_data_ingestion",
    srcs = ["MarketDataIngestion.java"],
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
    deps = [
        "@maven//:com_google_inject_guice",
        "@maven//:io_reactivex_rxjava3_rxjava",
        "@maven//:org_knowm_xchange_xchange_core",
        "@maven//:org_knowm_xchange_xchange_stream_coinbasepro",
        "@maven//:org_knowm_xchange_xchange_stream_core",
        "//protos:marketdata_java_proto",
        ":candle_manager",
        ":candle_publisher",
        ":currency_pair_supplier",
        ":market_data_ingestion",
        ":thin_market_timer",
        ":trade_processor",
    ],
)

java_library(
    name = "run_mode",
    srcs = ["RunMode.java"],
)

java_library(
    name = "streaming_exchange_provider",
    srcs = ["StreamingExchangeProvider.java"],
    deps = [
        "@maven//:com_google_inject_guice",
        "@maven//:org_knowm_xchange_xchange_core",
        "@maven//:org_knowm_xchange_xchange_stream_core",
        "@maven//:net_sourceforge_argparse4j_argparse4j",
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
        "@maven//:com_google_inject_guice",
        "@maven//:org_knowm_xchange_xchange_core",
        ":thin_market_timer",
        ":thin_market_timer_task",
    ]
)

java_library(
    name = "thin_market_timer_task",
    srcs = ["ThinMarketTimerTask.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_guice",
        "@maven//:org_knowm_xchange_xchange_core",
        ":candle_manager",
        ":currency_pair_supplier",
        ":thin_market_timer",
    ]
)

java_library(
    name = "trade_processor",
    srcs = ["TradeProcessor.java"],
    deps = [
        "//:autovalue",
        "//protos:marketdata_java_proto",
    ],
)
