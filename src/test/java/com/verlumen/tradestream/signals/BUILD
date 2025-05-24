load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "GenerateTradeSignalsTest",
    srcs = ["GenerateTradeSignalsTest.java"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//protos:trade_signals_java_proto",
        "//src/main/java/com/verlumen/tradestream/signals:generate_trade_signals",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_state",
        "//src/main/java/com/verlumen/tradestream/ta4j:bar_series_factory",
        "//src/main/java/com/verlumen/tradestream/ta4j:ta4j_module",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "PublishTradeSignalsTest",
    srcs = ["PublishTradeSignalsTest.java"],
    runtime_deps = [
        "//third_party/java:beam_runners_direct_java",
        "//third_party/java:hamcrest",
    ],
    deps = [
        "//protos:strategies_java_proto",
        "//protos:trade_signals_java_proto",
        "//src/main/java/com/verlumen/tradestream/signals:publish_trade_signals",
        "//src/main/java/com/verlumen/tradestream/signals:trade_signal_publisher",
        "//third_party/java:beam_sdks_java_core",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:junit",
        "//third_party/java:kafka_clients",
        "//third_party/java:mockito_core",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "TradeSignalPublisherImplTest",
    srcs = ["TradeSignalPublisherImplTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//protos:trade_signals_java_proto",
        "//src/main/java/com/verlumen/tradestream/signals:trade_signal_publisher",
        "//src/main/java/com/verlumen/tradestream/signals:trade_signal_publisher_impl",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:guice_testlib",
        "//third_party/java:junit",
        "//third_party/java:kafka_clients",
        "//third_party/java:mockito_core",
        "//third_party/java:truth",
    ],
)
