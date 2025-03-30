load("@rules_java//java:defs.bzl", "java_test")


java_test(
    name = "CandleStreamWithDefaultsTest",
    srcs = ["CandleStreamWithDefaultsTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_stream_with_defaults",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:guava",
        "//third_party:joda_time",
        "//third_party:junit",
        "//third_party:protobuf_java",
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
        "//third_party:hamcrest",
    ],
)

java_test(
    name = "CoinbaseStreamingClientTest",
    srcs = ["CoinbaseStreamingClientTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//src/main/java/com/verlumen/tradestream/marketdata:coinbase_streaming_client",
        "//src/main/java/com/verlumen/tradestream/marketdata:exchange_streaming_client",
        "//third_party:gson",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:truth",
    ],
)

java_test(
    name = "DefaultTradeGeneratorTest",
    srcs = ["DefaultTradeGeneratorTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:default_trade_generator",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:joda_time",
        "//third_party:junit",
        "//third_party:protobuf_java",
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
        "//third_party:hamcrest",
    ],
)

java_test(
    name = "ExchangeClientUnboundedSourceImplTest",
    srcs = ["ExchangeClientUnboundedSourceImplTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair_supply",
        "//src/main/java/com/verlumen/tradestream/marketdata:exchange_client_unbounded_reader",
        "//src/main/java/com/verlumen/tradestream/marketdata:exchange_client_unbounded_source",
        "//src/main/java/com/verlumen/tradestream/marketdata:exchange_client_unbounded_source_impl",
        "//src/main/java/com/verlumen/tradestream/marketdata:exchange_streaming_client",
        "//src/main/java/com/verlumen/tradestream/marketdata:trade_checkpoint_mark",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:beam_sdks_java_test_utils",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:joda_time",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:protobuf_java",
        "//third_party:protobuf_java_util",
        "//third_party:truth",
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
        "//third_party:hamcrest",
    ],
)

java_test(
    name = "LastCandlesFnTest",
    srcs = ["LastCandlesFnTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:last_candles_fn",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:beam_sdks_java_test_utils",
        "//third_party:guava",
        "//third_party:joda_time",
        "//third_party:junit",
        "//third_party:protobuf_java",
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
        "//third_party:hamcrest",
    ],
)

java_test(
    name = "MultiTimeframeCandleTransformTest",
    srcs = ["MultiTimeframeCandleTransformTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:multi_timeframe_candle_transform",
        "//src/main/java/com/verlumen/tradestream/time:time_frame",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:guava",
        "//third_party:joda_time",
        "//third_party:junit",
        "//third_party:protobuf_java",
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
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:beam_sdks_java_test_utils",
        "//third_party:joda_time",
        "//third_party:junit",
        "//third_party:protobuf_java",
        "//third_party:guava",
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
        "//third_party:hamcrest",
    ],
)
