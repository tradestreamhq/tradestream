load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "DoubleEmaCrossoverStrategyTest",
    srcs = ["DoubleEmaCrossoverStrategyTest.java"],
    deps = [
        "@maven//:com_google_truth_truth",
        "@maven//:junit_junit",
        "@maven//:org_mockito_mockito_core",
        "@maven//:org_ta4j_ta4j_core",
        "//src/main/java/com/verlumen/tradestream/strategies/movingaverages:movingaverages_lib",
    ],
    runtime_deps = [
        "@maven//:com_google_flogger_flogger_system_backend",
    ],
)
