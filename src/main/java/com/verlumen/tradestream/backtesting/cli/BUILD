load("@rules_java//java:defs.bzl", "java_binary")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

kt_jvm_library(
    name = "backtest_cli_lib",
    srcs = ["BacktestCli.kt"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtest_runner_impl",
        "//src/main/java/com/verlumen/tradestream/backtesting:backtesting_module",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_specs",
        "//src/main/java/com/verlumen/tradestream/ta4j:ta4j_module",
        "//third_party/java:argparse4j",
        "//third_party/java:flogger",
        "//third_party/java:gson",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
    ],
)

java_binary(
    name = "backtest_cli",
    data = [
        "//fixtures:marketdata",
    ],
    main_class = "com.verlumen.tradestream.backtesting.cli.BacktestCli",
    runtime_deps = [
        ":backtest_cli_lib",
    ],
)
