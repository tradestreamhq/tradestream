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
    name = "VolumeWeightedMacdLineIndicatorTest",
    srcs = ["VolumeWeightedMacdLineIndicatorTest.java"],
    test_class = "com.verlumen.tradestream.ta4j.VolumeWeightedMacdLineIndicatorTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/ta4j:volume_weighted_macd_line_indicator",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
