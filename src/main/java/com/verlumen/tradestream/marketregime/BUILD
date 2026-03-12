load("@rules_java//java:defs.bzl", "java_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "market_regime",
    srcs = ["MarketRegime.java"],
)

java_library(
    name = "regime_classification",
    srcs = ["RegimeClassification.java"],
    deps = [
        ":market_regime",
        "//third_party/java:guava",
    ],
)

java_library(
    name = "regime_change_event",
    srcs = ["RegimeChangeEvent.java"],
    deps = [
        ":regime_classification",
        "//third_party/java:guava",
    ],
)

java_library(
    name = "market_regime_detector",
    srcs = ["MarketRegimeDetector.java"],
    deps = [
        ":market_regime",
        ":regime_change_event",
        ":regime_classification",
        "//third_party/java:guava",
        "//third_party/java:ta4j_core",
    ],
)
