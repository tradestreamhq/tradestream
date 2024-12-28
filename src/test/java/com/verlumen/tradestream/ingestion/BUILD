load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "AppTest",
    srcs = [
      "AppTest.java"
    ],
    deps = [
        "//src/main/java/com/verlumen/tradestream/ingestion:app",
        "//src/main/java/com/verlumen/tradestream/ingestion:real_time_data_ingestion",
        "//src/main/java/com/verlumen/tradestream/ingestion:run_mode",
        "//third_party:guice_testlib",
        "//third_party:guice",
        "//third_party:truth",
        "//third_party:junit",
        "//third_party:mockito_core",
    ],
    runtime_deps = [
        "//third_party:flogger_system_backend",
    ],
)

java_test(
    name = "CandleBuilderTest",
    srcs = ["CandleBuilderTest.java"],
    deps = [
        "@tradestream_maven//:com_google_truth_truth",
        "@tradestream_maven//:com_google_testparameterinjector_test_parameter_injector",
        "@tradestream_maven//:junit_junit",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_builder",
    ],
)

java_test(
    name = "CandleManagerImplTest",
    srcs = ["CandleManagerImplTest.java"],
    deps = [
        "@tradestream_maven//:com_google_inject_extensions_guice_assistedinject",
        "@tradestream_maven//:com_google_inject_extensions_guice_testlib",
        "@tradestream_maven//:com_google_inject_guice",
        "@tradestream_maven//:com_google_truth_truth",
        "@tradestream_maven//:junit_junit",
        "@tradestream_maven//:org_mockito_mockito_core",
        "@tradestream_maven//:com_google_guava_guava",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager_impl",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher",
        "//src/main/java/com/verlumen/tradestream/ingestion:price_tracker",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
    ],
)

java_test(
    name = "CandlePublisherImplTest",
    srcs = ["CandlePublisherImplTest.java"],
    deps = [
        "@tradestream_maven//:com_google_inject_extensions_guice_assistedinject",
        "@tradestream_maven//:com_google_inject_extensions_guice_testlib",
        "@tradestream_maven//:com_google_inject_guice",
        "@tradestream_maven//:junit_junit",
        "@tradestream_maven//:org_apache_kafka_kafka_clients",
        "@tradestream_maven//:org_mockito_mockito_core",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher_impl",
    ],
)

java_test(
    name = "CoinbaseStreamingClientTest",
    srcs = ["CoinbaseStreamingClientTest.java"],
    deps = [
        "@tradestream_maven//:com_google_inject_extensions_guice_testlib",
        "@tradestream_maven//:com_google_inject_guice",
        "@tradestream_maven//:com_google_truth_truth",
        "@tradestream_maven//:junit_junit",
        "@tradestream_maven//:org_mockito_mockito_core",
        "@tradestream_maven//:com_google_code_gson_gson",
        "@tradestream_maven//:com_google_guava_guava",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:coinbase_streaming_client",
        "//src/main/java/com/verlumen/tradestream/ingestion:exchange_streaming_client",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
    ],
)

java_test(
    name = "HttpClientImplTest",
    srcs = ["HttpClientImplTest.java"],
    deps = [
        "@tradestream_maven//:com_google_inject_extensions_guice_testlib",
        "@tradestream_maven//:com_google_inject_guice",
        "@tradestream_maven//:com_google_truth_truth",
        "@tradestream_maven//:junit_junit",
        "@tradestream_maven//:org_mockito_mockito_core",
        "//src/main/java/com/verlumen/tradestream/ingestion:http_client_impl",
        "//src/main/java/com/verlumen/tradestream/ingestion:http_url_connection_factory",
    ],
)

java_test(
    name = "KafkaPropertiesTest",
    srcs = ["KafkaPropertiesTest.java"],
    deps = [
        "@tradestream_maven//:com_google_inject_extensions_guice_testlib",
        "@tradestream_maven//:com_google_inject_guice",
        "@tradestream_maven//:com_google_truth_truth",
        "@tradestream_maven//:net_sourceforge_argparse4j_argparse4j",
        "//src/main/java/com/verlumen/tradestream/ingestion:kafka_properties",
    ],
)

java_test(
    name = "PriceTrackerTest",
    srcs = ["PriceTrackerTest.java"],
    deps = [
        "@tradestream_maven//:com_google_inject_guice",
        "@tradestream_maven//:com_google_truth_truth",
        "@tradestream_maven//:junit_junit",
        "//src/main/java/com/verlumen/tradestream/ingestion:price_tracker",
    ],
)

java_test(
    name = "RealTimeDataIngestionImplTest",
    srcs = ["RealTimeDataIngestionImplTest.java"],
    deps = [
        "@tradestream_maven//:com_google_guava_guava",
        "@tradestream_maven//:com_google_inject_extensions_guice_testlib",
        "@tradestream_maven//:com_google_inject_guice",
        "@tradestream_maven//:com_google_truth_truth",
        "@tradestream_maven//:junit_junit",
        "@tradestream_maven//:org_mockito_mockito_core",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher",
        "//src/main/java/com/verlumen/tradestream/ingestion:currency_pair_supply",
        "//src/main/java/com/verlumen/tradestream/ingestion:exchange_streaming_client",
        "//src/main/java/com/verlumen/tradestream/ingestion:thin_market_timer",
        "//src/main/java/com/verlumen/tradestream/ingestion:trade_processor",
        "//src/main/java/com/verlumen/tradestream/ingestion:real_time_data_ingestion_impl",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
    ],
)

java_test(
    name = "ThinMarketTimerImplTest",
    srcs = ["ThinMarketTimerImplTest.java"],
    deps = [
        "@tradestream_maven//:com_google_inject_extensions_guice_testlib",
        "@tradestream_maven//:com_google_inject_guice",
        "@tradestream_maven//:com_google_guava_guava",
        "@tradestream_maven//:com_google_truth_truth",
        "@tradestream_maven//:junit_junit",
        "@tradestream_maven//:org_mockito_mockito_core",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:thin_market_timer_impl",
        "//src/main/java/com/verlumen/tradestream/ingestion:thin_market_timer_task",
    ],
)

java_test(
    name = "ThinMarketTimerTaskImplTest",
    srcs = ["ThinMarketTimerTaskImplTest.java"],
    deps = [
        "@tradestream_maven//:com_google_guava_guava",
        "@tradestream_maven//:com_google_inject_extensions_guice_testlib",
        "@tradestream_maven//:com_google_inject_guice",
        "@tradestream_maven//:com_google_truth_truth",
        "@tradestream_maven//:junit_junit",
        "@tradestream_maven//:org_mockito_mockito_core",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:currency_pair_metadata",
        "//src/main/java/com/verlumen/tradestream/ingestion:currency_pair_supply",
        "//src/main/java/com/verlumen/tradestream/ingestion:thin_market_timer_task_impl",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
    ],
)

java_test(
    name = "TradeProcessorTest",
    srcs = ["TradeProcessorTest.java"],
    deps = [
        "@tradestream_maven//:com_google_truth_truth",
        "@tradestream_maven//:junit_junit",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:trade_processor",
    ],
)
