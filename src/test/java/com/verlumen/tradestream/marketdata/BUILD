"""Build rules for marketdata tests."""

load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_test")

kt_jvm_test(
    name = "InfluxDbCandleFetcherTest",
    srcs = ["InfluxDbCandleFetcherTest.kt"],
    test_class = "com.verlumen.tradestream.marketdata.InfluxDbCandleFetcherTest",
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:influxdb_candle_fetcher",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:guice_testlib",
        "//third_party/java:influxdb_client_java",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:truth",
    ],
)
