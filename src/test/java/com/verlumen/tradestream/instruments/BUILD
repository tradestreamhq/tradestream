load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "CurrencyPairTest",
    srcs = ["CurrencyPairTest.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/instruments:currency",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "InstrumentTest",
    srcs = ["InstrumentTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//src/main/java/com/verlumen/tradestream/instruments:currency_pair",
        "//src/main/java/com/verlumen/tradestream/instruments:instrument",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
)
