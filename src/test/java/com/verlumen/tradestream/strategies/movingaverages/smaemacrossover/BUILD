package(default_visibility = ["//src:__subpackages__"])

java_test(
    name = "SmaEmaCrossoverStrategyTest",
    srcs = glob(["*.java"]),
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/movingaverages/smaemacrossover:smaemacrossover_strategy_lib",
        "//protos:strategies_java_proto",
        "@maven//:org_junit_jupiter_api", // Using JUnit 5
    ],
)
