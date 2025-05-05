"""Build rules for marketdata tests."""

load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_test")
load("@rules_java//java:defs.bzl", "java_test")

kt_jvm_test(
    name = "CandleLookbackDoFnTest",
    srcs = ["CandleLookbackDoFnTest.kt"],
    # Ensure test class name matches the file
    test_class = "com.verlumen.tradestream.marketdata.CandleLookbackDoFnTest",
    deps = [
        # Dependency on the main library target
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_lookback_do_fn",
        # Test dependencies
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:beam_sdks_java_test_utils",
        "//third_party:guava",
        "//third_party:hamcrest",
        "//third_party:joda_time",
        "//third_party:junit",
        "//third_party:protobuf_java_util",
        "//third_party:truth",
        # Guice/Mockito aren't strictly needed by this test anymore
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
    ],
)

kt_jvm_test(
    name = "FillForwardCandlesTest",
    srcs = ["FillForwardCandlesTest.kt"],
    test_class = "com.verlumen.tradestream.marketdata.FillForwardCandlesTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/marketdata:fill_forward_candles",
        "//src/main/java/com/verlumen/tradestream/marketdata:fill_forward_candles_fn",
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:beam_sdks_java_test_utils",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:guice_testlib",
        "//third_party:hamcrest",
        "//third_party:joda_time",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:protobuf_java",
        "//third_party:protobuf_java_util",
        "//third_party:truth",
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
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
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_combine_fn",
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

kt_jvm_test(
    name = "TiingoCryptoFetcherFnTest",
    srcs = ["TiingoCryptoFetcherFnTest.kt"],
    test_class = "com.verlumen.tradestream.marketdata.TiingoCryptoFetcherFnTest",
    deps = [
        # Main library target
        "//src/main/java/com/verlumen/tradestream/marketdata:tiingo_crypto_fetcher_fn",
        "//src/main/java/com/verlumen/tradestream/http:http_client",
        "//protos:marketdata_java_proto",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_test_utils",
        "//third_party:guava",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:protobuf_java_util",
        "//third_party:truth",
        "//third_party:joda_time",
    ],
    runtime_deps = [
         "//third_party:beam_runners_direct_java",
         "//third_party:hamcrest",
    ],
)

kt_jvm_test(
    name = "TiingoResponseParserTest",
    srcs = ["TiingoResponseParserTest.kt"],
    test_class = "com.verlumen.tradestream.marketdata.TiingoResponseParserTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/marketdata:tiingo_response_parser",
        "//protos:marketdata_java_proto",
        "//third_party:gson",
        "//third_party:junit",
        "//third_party:protobuf_java",
        "//third_party:protobuf_java_util",
        "//third_party:truth",
    ],
)

kt_jvm_test(
    name = "TradeToCandleTest",
    srcs = ["TradeToCandleTest.kt"],
    test_class = "com.verlumen.tradestream.marketdata.TradeToCandleTest",
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_combine_fn",
        "//src/main/java/com/verlumen/tradestream/marketdata:market_data_module",
        "//src/main/java/com/verlumen/tradestream/marketdata:trade_to_candle",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:beam_sdks_java_test_utils",
        "//third_party:flogger",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:guice_testlib",
        "//third_party:hamcrest",
        "//third_party:joda_time",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:protobuf_java",
        "//third_party:protobuf_java_util",
        "//third_party:truth",
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
    ],
)
