"""Build rules for marketdata tests."""

load("@rules_java//java:defs.bzl", "java_test")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_test")

kt_jvm_test(
    name = "CandleLookbackDoFnTest",
    srcs = ["CandleLookbackDoFnTest.kt"],
    # Ensure test class name matches the file
    test_class = "com.verlumen.tradestream.marketdata.CandleLookbackDoFnTest",
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
    ],
    deps = [
        # Dependency on the main library target
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_lookback_do_fn",
        # Test dependencies
        "//protos:marketdata_java_proto",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:guava",
        "//third_party/java:hamcrest",
        "//third_party/java:joda_time",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:truth",
        # Guice/Mockito aren't strictly needed by this test anymore
    ],
)

kt_jvm_test(
    name = "FillForwardCandlesTest",
    srcs = ["FillForwardCandlesTest.kt"],
    test_class = "com.verlumen.tradestream.marketdata.FillForwardCandlesTest",
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
    ],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:fill_forward_candles",
        "//src/main/java/com/verlumen/tradestream/marketdata:fill_forward_candles_fn",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:guice_testlib",
        "//third_party/java:hamcrest",
        "//third_party/java:joda_time",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "DefaultTradeGeneratorTest",
    srcs = ["DefaultTradeGeneratorTest.java"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:default_trade_generator",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:joda_time",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
    ],
)

java_test(
    name = "LastCandlesFnTest",
    srcs = ["LastCandlesFnTest.java"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:last_candles_fn",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:guava",
        "//third_party/java:joda_time",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
    ],
)

java_test(
    name = "SlidingCandleAggregatorTest",
    srcs = ["SlidingCandleAggregatorTest.java"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_combine_fn",
        "//src/main/java/com/verlumen/tradestream/marketdata:sliding_candle_aggregator",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:guava",
        "//third_party/java:joda_time",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
    ],
)

kt_jvm_test(
    name = "TiingoCryptoCandleTransformTest",
    srcs = ["TiingoCryptoCandleTransformTest.kt"],
    test_class = "com.verlumen.tradestream.marketdata.TiingoCryptoCandleTransformTest",
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/http:http_client",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//src/main/java/com/verlumen/tradestream/marketdata:tiingo_crypto_candle_transform",
        "//src/main/java/com/verlumen/tradestream/marketdata:tiingo_crypto_fetcher_fn",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:joda_time",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:mockito_kotlin",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:truth",
    ],
)

kt_jvm_test(
    name = "TiingoCryptoFetcherFnTest",
    srcs = ["TiingoCryptoFetcherFnTest.kt"],
    test_class = "com.verlumen.tradestream.marketdata.TiingoCryptoFetcherFnTest",
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/http:http_client",
        "//src/main/java/com/verlumen/tradestream/marketdata:tiingo_crypto_fetcher_fn",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:joda_time",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:mockito_kotlin",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:truth",
    ],
)

kt_jvm_test(
    name = "TiingoResponseParserTest",
    srcs = ["TiingoResponseParserTest.kt"],
    test_class = "com.verlumen.tradestream.marketdata.TiingoResponseParserTest",
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/marketdata:tiingo_response_parser",
        "//third_party/java:gson",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:truth",
    ],
)

kt_jvm_test(
    name = "TradeToCandleTest",
    srcs = ["TradeToCandleTest.kt"],
    test_class = "com.verlumen.tradestream.marketdata.TradeToCandleTest",
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
    ],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//src/main/java/com/verlumen/tradestream/marketdata:candle_combine_fn",
        "//src/main/java/com/verlumen/tradestream/marketdata:market_data_module",
        "//src/main/java/com/verlumen/tradestream/marketdata:trade_to_candle",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:beam_sdks_java_extensions_protobuf",
        "//third_party/java:beam_sdks_java_test_utils",
        "//third_party/java:flogger",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:guice_testlib",
        "//third_party/java:hamcrest",
        "//third_party/java:joda_time",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:truth",
    ],
)
