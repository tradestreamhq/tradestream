load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "AppTest",
    srcs = [
      "AppTest.java"
    ],
    deps = [
        "@maven//:com_google_inject_extensions_guice_testlib",
        "@maven//:com_google_inject_guice",
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "@maven//:org_mockito_mockito_core",
        "//src/main/java/com/verlumen/tradestream/ingestion:app",
        "//src/main/java/com/verlumen/tradestream/ingestion:market_data_ingestion",
        "//src/main/java/com/verlumen/tradestream/ingestion:run_mode",
    ],
    runtime_deps = [
        "@maven//:com_google_flogger_flogger_system_backend",
    ],
)

java_test(
    name = "CandleBuilderTest",
    srcs = ["CandleBuilderTest.java"],
    deps = [
        "@maven//:com_google_truth_truth",
        "@maven//:com_google_testparameterinjector_test_parameter_injector",
        "@maven//:junit_junit",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_builder",
    ],
)

java_test(
    name = "CandleManagerImplTest",
    srcs = ["CandleManagerImplTest.java"],
    deps = [
        "@maven//:com_google_inject_extensions_guice_assistedinject",
        "@maven//:com_google_inject_extensions_guice_testlib",
        "@maven//:com_google_inject_guice",
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "@maven//:org_mockito_mockito_core",
        "@maven//:com_google_guava_guava",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager_impl",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher",
        "//src/main/java/com/verlumen/tradestream/ingestion:price_tracker",
    ],
)

java_test(
    name = "CandlePublisherImplTest",
    srcs = ["CandlePublisherImplTest.java"],
    deps = [
        "@maven//:com_google_inject_extensions_guice_assistedinject",
        "@maven//:com_google_inject_extensions_guice_testlib",
        "@maven//:com_google_inject_guice",
        "@maven//:junit_junit",
        "@maven//:org_apache_kafka_kafka_clients",
        "@maven//:org_mockito_mockito_core",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher_impl",
    ],
)

java_test(
    name = "KafkaPropertiesTest",
    srcs = ["KafkaPropertiesTest.java"],
    deps = [
        "@maven//:com_google_inject_extensions_guice_testlib",
        "@maven//:com_google_inject_guice",
        "@maven//:com_google_truth_truth",
        "@maven//:net_sourceforge_argparse4j_argparse4j",
        "//src/main/java/com/verlumen/tradestream/ingestion:kafka_properties",
    ],
)

java_test(
    name = "PriceTrackerTest",
    srcs = ["PriceTrackerTest.java"],
    deps = [
        "@maven//:com_google_inject_guice",
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "//src/main/java/com/verlumen/tradestream/ingestion:price_tracker",
    ],
)

java_test(
    name = "RealTimeDataIngestionImplTest",
    srcs = ["RealTimeDataIngestionImplTest.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_extensions_guice_testlib",
        "@maven//:com_google_inject_guice",
        "@maven//:com_google_truth_truth",
        "@maven//:io_reactivex_rxjava3_rxjava",
        "@maven//:junit_junit",
        "@maven//:org_knowm_xchange_xchange_core",
        "@maven//:org_knowm_xchange_xchange_stream_core",
        "@maven//:org_mockito_mockito_core",
        "//protos:marketdata_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher",
        "//src/main/java/com/verlumen/tradestream/ingestion:currency_pair_supplier",
        "//src/main/java/com/verlumen/tradestream/ingestion:thin_market_timer",
        "//src/main/java/com/verlumen/tradestream/ingestion:trade_processor",
        "//src/main/java/com/verlumen/tradestream/ingestion:real_time_data_ingestion_impl",
    ],
)

java_test(
    name = "ThinMarketTimerImplTest",
    srcs = ["ThinMarketTimerImplTest.java"],
    deps = [
        "@maven//:com_google_inject_extensions_guice_testlib",
        "@maven//:com_google_inject_guice",
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "@maven//:org_mockito_mockito_core",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:currency_pair_supplier",
        "//src/main/java/com/verlumen/tradestream/ingestion:thin_market_timer_impl",
        "//src/main/java/com/verlumen/tradestream/ingestion:thin_market_timer_task",
    ],
)

java_test(
    name = "ThinMarketTimerTaskImplTest",
    srcs = ["ThinMarketTimerTaskImplTest.java"],
    deps = [
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_inject_extensions_guice_testlib",
        "@maven//:com_google_inject_guice",
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "@maven//:org_knowm_xchange_xchange_core",
        "@maven//:org_mockito_mockito_core",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:currency_pair_supplier",
        "//src/main/java/com/verlumen/tradestream/ingestion:thin_market_timer_task_impl",
    ],
)

java_test(
    name = "TradeProcessorTest",
    srcs = ["TradeProcessorTest.java"],
    deps = [
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:trade_processor",
    ],
)
