load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_test")

kt_jvm_test(
    name = "BacktestCliTest",
    srcs = ["BacktestCliTest.kt"],
    data = [
        "//fixtures:marketdata",
    ],
    tags = ["block-network"],
    test_class = "com.verlumen.tradestream.backtesting.cli.BacktestCliTest",
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//src/main/java/com/verlumen/tradestream/backtesting/cli:backtest_cli_lib",
        "//third_party/java:gson",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
)
