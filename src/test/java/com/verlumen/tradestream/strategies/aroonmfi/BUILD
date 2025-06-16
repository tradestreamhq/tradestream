package(default_visibility = ["//src:__subpackages__"])

java_test(
    name = "AroonMfiStrategyTest",
    srcs = glob(["*.java"]),
    test_class = "com.verlumen.tradestream.strategies.aroonmfi.AroonMfiStrategyTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/aroonmfi:aroonmfi_strategy_lib",
        "//protos:strategies_java_proto",
        "@maven//:org_junit_jupiter_api", # For JUnit 5 annotations and assertions
        "//third_party/java:ta4j_core", # For BaseBarSeries in test
    ],
)
