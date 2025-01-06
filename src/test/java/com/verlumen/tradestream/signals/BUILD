load("@rules_java//java:defs.bzl", "java_test")

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
