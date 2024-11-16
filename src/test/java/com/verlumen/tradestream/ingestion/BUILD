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
        "//src/main/java/com/verlumen/tradestream/ingestion:market-data-ingestion",
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
    name = "CandleManagerTest",
    srcs = ["CandleManagerTest.java"],
    deps = [
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "@maven//:org_mockito_mockito_core",
        "@maven//:com_google_testparameterinjector_test_parameter_injector",
        "@maven//:com_google_guava_guava",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle-manager",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher_impl",
        "//src/main/java/com/verlumen/tradestream/ingestion:price_tracker",
    ],
)

java_test(
    name = "CandlePublisherImplTest",
    srcs = ["CandlePublisherImplTest.java"],
    deps = [
        "@maven//:com_google_testparameterinjector_test_parameter_injector",
        "@maven//:junit_junit",
        "@maven//:org_apache_kafka_kafka_clients",
        "@maven//:org_mockito_mockito_core",
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle_publisher_impl",
    ],
)

java_test(
    name = "PriceTrackerTest",
    srcs = ["PriceTrackerTest.java"],
    deps = [
        "@maven//:com_google_inject_guice",
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "@maven//:com_google_testparameterinjector_test_parameter_injector",
        "//src/main/java/com/verlumen/tradestream/ingestion:price_tracker",
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
