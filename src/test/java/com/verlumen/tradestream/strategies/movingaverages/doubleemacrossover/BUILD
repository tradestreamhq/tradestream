package(default_visibility = ["//src:__subpackages__"])

java_test(
    name = "DoubleEmaCrossoverStrategyTest",
    srcs = glob(["*.java"]),
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies/movingaverages/doubleemacrossover:doubleemacrossover_strategy_lib",
        "//protos:strategies_java_proto",
        "@maven//:org_junit_jupiter_api", # As per subtask for JUnit 5
    ],
)
