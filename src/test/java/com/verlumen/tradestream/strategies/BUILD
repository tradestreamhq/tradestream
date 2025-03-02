load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "MarketDataConsumerImplTest",
    srcs = ["MarketDataConsumerImplTest.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies:market_data_consumer",
        "//src/main/java/com/verlumen/tradestream/strategies:market_data_consumer_impl",
        "//third_party:guice_assistedinject",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:kafka_clients",
        "//third_party:mockito_core",
    ],
)

java_test(
    name = "StrategyEngineImplTest",
    srcs = ["StrategyEngineImplTest.java"],
    deps = [
        "//protos:backtesting_java_proto",
        "//protos:marketdata_java_proto",
        "//protos:strategies_java_proto",
        "//protos:trade_signals_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:genetic_algorithm_orchestrator",
        "//src/main/java/com/verlumen/tradestream/signals:trade_signal_publisher",
        "//src/main/java/com/verlumen/tradestream/strategies:candle_buffer",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_engine",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_engine_impl",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_manager",
        "//third_party:guava",
        "//third_party:guice",
        "//third_party:guice_testlib",
        "//third_party:junit",
        "//third_party:mockito_core",
        "//third_party:protobuf_java",
        "//third_party:protobuf_java_util",
        "//third_party:ta4j_core",
        "//third_party:truth",
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
