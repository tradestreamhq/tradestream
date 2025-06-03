load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = [
    "//src/test/java/com/verlumen/tradestream/signals:__pkg__",
])

java_library(
    name = "signals_module",
    visibility = [
        "//src/test/java/com/verlumen/tradestream/pipeline:__pkg__",
    ],
    deps = [
        ":trade_signal_publisher",
        ":trade_signal_publisher_impl",
        "//third_party/java:auto_value",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
    ],
)

java_library(
    name = "trade_signal_publisher",
    srcs = ["TradeSignalPublisher.java"],
    deps = [
        "//protos:trade_signals_java_proto",
    ],
)

java_library(
    name = "trade_signal_publisher_impl",
    srcs = ["TradeSignalPublisherImpl.java"],
    deps = [
        ":trade_signal_publisher",
        "//protos:trade_signals_java_proto",
        "//third_party/java:flogger",
        "//third_party/java:guice",
        "//third_party/java:guice_assistedinject",
        "//third_party/java:kafka_clients",
        "//third_party/java:protobuf_java_util",
    ],
)
