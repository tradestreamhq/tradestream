load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "OptimizeStrategiesTest",
    srcs = ["OptimizeStrategiesTest.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:genetic_algorithm_orchestrator",
        "//src/main/java/com/verlumen/tradestream/strategies:optimize_strategies",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_record",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_state",
        "//src/main/java/com/verlumen/tradestream/ta4j:ta4j_module",
        "//third_party:beam_sdks_java_core",
        "//third_party:beam_sdks_java_extensions_protobuf",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:protobuf_java",
        "//third_party:ta4j_core",
        "//third_party:truth",
    ],
    runtime_deps = [
        "//third_party:beam_runners_direct_java",
        "//third_party:hamcrest",
    ],
)

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
)

java_test(
    name = "StrategyFactoriesTest",
    srcs = ["StrategyFactoriesTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_constants",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factories",
        "//third_party:guava",
        "//third_party:junit",
        "//third_party:test_parameter_injector",
        "//third_party:truth",
    ],
)

java_test(
    name = "StrategyStateFactoryImplTest",
    srcs = ["StrategyStateFactoryImplTest.java"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_factory",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_state",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_state_factory_impl",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:protobuf_java",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:ta4j_core",
        "//third_party:truth",
    ],
)
