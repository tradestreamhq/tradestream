load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_test")

kt_jvm_test(
    name = "StrategySpecsTest",
    srcs = ["StrategySpecsTest.kt"],
    test_class = "com.verlumen.tradestream.strategies.StrategySpecsTest",
    deps = [
        # The protobuf enum definition for StrategyType
        "//protos:strategies_java_proto",

        # The library under test, which contains the .spec and .isSupported() extensions
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_specs",

        # Testing libraries
        "//third_party/java:junit",
        "//third_party/java:test_parameter_injector",
        "//third_party/java:truth",
    ],
)
