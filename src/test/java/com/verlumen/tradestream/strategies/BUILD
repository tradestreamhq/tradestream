load("@rules_java//java:defs.bzl", "java_test")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_test")

java_test(
    name = "StrategyManagerImplTest",
    srcs = ["StrategyManagerImplTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager_impl",
        "//third_party/java:flogger",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:guice_testlib",
        "//third_party/java:junit",
        "//third_party/java:mockito_core",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "StrategyFactoriesTest",
    srcs = ["StrategyFactoriesTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_constants",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factories",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//third_party/java:guava",
        "//third_party/java:junit",
        "//third_party/java:test_parameter_injector",
        "//third_party/java:truth",
    ],
)

kt_jvm_test(
    name = "StrategySpecsTest",
    srcs = ["StrategySpecsTest.kt"],
    test_class = "com.verlumen.tradestream.strategies.StrategySpecsTest",
    deps = [
        # The protobuf enum definition for StrategyType
        "//protos:strategies_java_proto",

        # The library under test, which contains the .spec and .isSupported() extensions
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_specs",

        # JUnit and TestParameterInjector for running the parameterized test
        "//third_party/java:junit",
        "//third_party/java:test_parameter_injector",
    ],
)
