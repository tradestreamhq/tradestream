load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "AppTest",
    srcs = [
      "AppTest.java"
    ],
    deps = [
        "//src/main/java/com/verlumen/tradestream/execution:run_mode",
        "//src/main/java/com/verlumen/tradestream/ingestion:app",
        "//src/main/java/com/verlumen/tradestream/ingestion:real_time_data_ingestion",
        "//third_party:flogger",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:truth",
    ],
    runtime_deps = [
        "//third_party:argparse4j",
    ],
)

java_test(
    name = "CandleBuilderTest",
    srcs = ["CandleBuilderTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_builder",
        "//third_party:junit",
        "//third_party:protobuf_java",
        "//third_party:protobuf_java_util",
        "//third_party:test_parameter_injector",
        "//third_party:truth",
    ],
)

java_test(
    name = "CandleManagerImplTest",
    srcs = ["CandleManagerImplTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager_impl",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher",
        "//src/main/java/com/verlumen/tradestream/ingestion:price_tracker",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:protobuf_java",
        "//third_party:protobuf_java_util",
        "//third_party:truth",
    ],
)

java_test(
    name = "CandlePublisherImplTest",
    srcs = ["CandlePublisherImplTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher_impl",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:kafka_clients",
        "//third_party:mockito_core",
        "//third_party:protobuf_java_util",
    ],
)

java_test(
    name = "CoinbaseStreamingClientTest",
    srcs = ["CoinbaseStreamingClientTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:coinbase_streaming_client",
        "//src/main/java/com/verlumen/tradestream/ingestion:exchange_streaming_client",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:gson",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:truth",
    ],
)

java_test(
    name = "PriceTrackerTest",
    srcs = ["PriceTrackerTest.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/ingestion:price_tracker",
        "//third_party:guice",
        "//third_party:junit",
        "//third_party:truth",
    ],
)

java_test(
    name = "RealTimeDataIngestionImplTest",
    srcs = ["RealTimeDataIngestionImplTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher",
        "//src/main/java/com/verlumen/tradestream/ingestion:currency_pair_supply",
        "//src/main/java/com/verlumen/tradestream/ingestion:exchange_streaming_client",
        "//src/main/java/com/verlumen/tradestream/ingestion:thin_market_timer",
        "//src/main/java/com/verlumen/tradestream/ingestion:trade_processor",
        "//src/main/java/com/verlumen/tradestream/ingestion:real_time_data_ingestion_impl",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:truth",
    ],
)

java_test(
    name = "ThinMarketTimerImplTest",
    srcs = ["ThinMarketTimerImplTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:thin_market_timer_impl",
        "//src/main/java/com/verlumen/tradestream/ingestion:thin_market_timer_task",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:truth",
    ],
)

java_test(
    name = "ThinMarketTimerTaskImplTest",
    srcs = ["ThinMarketTimerTaskImplTest.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:currency_pair_metadata",
        "//src/main/java/com/verlumen/tradestream/ingestion:currency_pair_supply",
        "//src/main/java/com/verlumen/tradestream/ingestion:thin_market_timer_task_impl",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:truth",
    ],
)

java_test(
    name = "TradeProcessorTest",
    srcs = ["TradeProcessorTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:trade_processor",
        "//third_party:junit",
        "//third_party:protobuf_java_util",
        "//third_party:truth",
    ],
)
