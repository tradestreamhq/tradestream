load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "CandleAuthorTest",
    srcs = [
      "CandleAuthorTest.java"
    ],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_author",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:beam_sdks_java_test_utils",
        "//third_party:protobuf_java",
        "//third_party:protobuf_java_util",
        "//third_party:joda_time",
        "//third_party:junit",
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
        "//third_party:hamcrest",
    ],
)
