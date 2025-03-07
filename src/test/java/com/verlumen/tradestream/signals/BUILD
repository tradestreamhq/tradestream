load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "GenerateTradeSignalsTest",
    srcs = ["GenerateTradeSignalsTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//protos:trade_signals_java_proto",
        "//src/main/java/com/verlumen/tradestream/signals:generate_trade_signals",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_state",
        "//src/main/java/com/verlumen/tradestream/ta4j:ta4j_module",
        "//third_party:beam_sdks_java_core",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
        "//third_party:truth",
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
        "//third_party:hamcrest",
    ],
)

java_test(
    name = "TradeSignalPublisherImplTest",
    srcs = ["TradeSignalPublisherImplTest.java"],
    deps = [
        "//protos:trade_signals_java_proto",
        "//protos:strategies_java_proto",
        "//third_party:guice",
        "//third_party:guice_assistedinject",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:kafka_clients",
        "//third_party:mockito_core",
        "//third_party:truth",
        "//src/main/java/com/verlumen/tradestream/signals:trade_signal_publisher",
        "//src/main/java/com/verlumen/tradestream/signals:trade_signal_publisher_impl",
    ],
)
