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
        "//src/main/java/com/verlumen/tradestream/ingestion:app-lib",
        "//src/main/java/com/verlumen/tradestream/ingestion:market-data-ingestion",
    ],
)

java_test(
    name = "CandleKeyTest",
    srcs = [
      "CandleKeyTest.java"
    ],
    deps = [
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_testparameterinjector_test_parameter_injector",
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle-key",
    ],
)

java_test(
    name = "RealTimeDataIngestionIntegrationTest",
    srcs = ["RealTimeDataIngestionIntegrationTest.java"],
    deps = [
        ":real-time-data-ingestion",
        ":candle-manager",
        ":trade-processor",
        ":candle-publisher",
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "@maven//:org_mockito_mockito_core",
        "@maven//:com_google_testparameterinjector_test_parameter_injector",
        "@maven//:com_google_guava_guava",
        "@maven//:org_knowm_xchange_xchange_core",
        "@maven//:org_knowm_xchange_xchange_stream_core",
        "@maven//:io_reactivex_rxjava3_rxjava",
        "//protos:marketdata_java_proto",
    ],
)
