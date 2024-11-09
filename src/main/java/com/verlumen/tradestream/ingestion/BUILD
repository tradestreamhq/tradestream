load("@rules_java//java:defs.bzl", "java_binary", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "candle-key",
    srcs = ["CandleKey.java"]
)

java_library(
    name = "real-time-data-ingestion-lib",
    srcs = ["RealTimeDataIngestion.java"],
    deps = [
        "@maven//:com_google_inject_guice",
    ]
)

java_binary(
    name = "real-time-data-ingestion",
    main_class = "com.verlumen.tradestream.RealTimeDataIngestion",
    runtime_deps = [":real-time-data-ingestion-lib"],
)
