load("@rules_java//java:defs.bzl", "java_test")

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
    name = "RealTimeDataIngestionTest",
    srcs = [
      "RealTimeDataIngestionTest.java"
    ],
    deps = [
        "@maven//:com_google_guava_guava",
        "@maven//:com_google_testparameterinjector_test_parameter_injector",
        "@maven//:com_google_truth_truth",
        "@maven//:io_reactivex_rxjava3_rxjava",
        "@maven//:junit_junit",
        "//src/main/java/com/verlumen/tradestream/ingestion:candle-key",
    ],
)
