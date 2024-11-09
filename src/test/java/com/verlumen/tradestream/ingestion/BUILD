load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "AppTest",
    srcs = [
      "AppTest.java"
    ],
    deps = [
        "@maven//:com_google_inject_guice",
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "//src/main/java/com/verlumen/tradestream/ingestion:app-lib",
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
