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
    name = "RealTimeDataIngestionImplTest",
    srcs = ["RealTimeDataIngestionImplTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ingestion:currency_pair_supply",
        "//src/main/java/com/verlumen/tradestream/ingestion:exchange_streaming_client",
        "//src/main/java/com/verlumen/tradestream/ingestion:real_time_data_ingestion_impl",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//src/main/java/com/verlumen/tradestream/marketdata:trade_publisher",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:truth",
    ],
)
