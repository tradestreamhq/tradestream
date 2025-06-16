package(default_visibility = ["//src:__subpackages__"])

java_test(
    name = "ParabolicSarStrategyTest",
    srcs = glob(["*.java"]),
    test_class = "com.verlumen.tradestream.strategies.parabolicsar.ParabolicSarStrategyTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/parabolicsar:parabolicsar_strategy_lib",
        "//protos:strategies_java_proto",
        "@maven//:org_junit_jupiter_api", # For JUnit 5 annotations and assertions
        "//third_party/java:ta4j_core", # For BaseBarSeries in test
    ],
)
