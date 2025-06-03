load("@rules_java//java:defs.bzl", "java_test")

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
