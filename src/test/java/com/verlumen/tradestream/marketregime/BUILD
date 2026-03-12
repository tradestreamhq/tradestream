load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "MarketRegimeDetectorTest",
    srcs = ["MarketRegimeDetectorTest.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/marketregime:market_regime",
        "//src/main/java/com/verlumen/tradestream/marketregime:market_regime_detector",
        "//src/main/java/com/verlumen/tradestream/marketregime:regime_change_event",
        "//src/main/java/com/verlumen/tradestream/marketregime:regime_classification",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
