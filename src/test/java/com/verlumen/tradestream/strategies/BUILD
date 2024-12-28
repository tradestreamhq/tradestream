load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "StrategyManagerImplTest",
    srcs = ["StrategyManagerImplTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager_impl",
        "//third_party:flogger",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:protobuf_java",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:ta4j_core",
        "//third_party:truth",
    ],
    runtime_deps = [
        "//third_party:flogger_system_backend",
    ],
)
