load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "BarSeriesBuilderTest",
    srcs = ["BarSeriesBuilderTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/ta4j:bar_series_builder",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:ta4j_core",
    ],
)

java_test(
    name = "TestBarSeriesBuilderTest",
    srcs = ["TestBarSeriesBuilderTest.java"],
    test_class = "com.verlumen.tradestream.ta4j.TestBarSeriesBuilderTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/ta4j:test_bar_series_builder",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
