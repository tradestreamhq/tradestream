load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "CreateCandlesTest",
    srcs = [
      "CreateCandlesTest.java"
    ],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:create_candles",
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

java_test(
    name = "ParseTradesTest",
    srcs = ["ParseTradesTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:parse_trades",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_test_utils",
        "//third_party:protobuf_java",
        "//third_party:protobuf_java_util",
        "//third_party:junit",
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
        "//third_party:hamcrest",
    ],
)

java_test(
    name = "SlidingCandleAggregatorTest",
    srcs = ["SlidingCandleAggregatorTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:sliding_candle_aggregator",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_test_utils",
        "//third_party:junit",
        "//third_party:protobuf_java",
        "//third_party:guava",
    ],
)

java_test(
    name = "TradePublisherImplTest",
    srcs = ["TradePublisherImplTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:trade_publisher",
        "//src/main/java/com/verlumen/tradestream/marketdata:trade_publisher_impl",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:kafka_clients",
        "//third_party:mockito_core",
        "//third_party:protobuf_java_util",
    ],
)
