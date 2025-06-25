load("@rules_java//java:defs.bzl", "java_test")
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

        # Renkochart tests
        "//src/test/java/com/verlumen/tradestream/strategies/renkochart:param_config_test",
        "//src/test/java/com/verlumen/tradestream/strategies/renkochart:strategy_factory_test",

        # Gannswing tests
        "//src/test/java/com/verlumen/tradestream/strategies/gannswing:param_config_test",
        "//src/test/java/com/verlumen/tradestream/strategies/gannswing:strategy_factory_test",
        # Sarmfi tests
        "//src/test/java/com/verlumen/tradestream/strategies/sarmfi:param_config_test",
        "//src/test/java/com/verlumen/tradestream/strategies/sarmfi:strategy_factory_test",
    ],
)

kt_jvm_test(
    name = "StrategyParameterTypeRegistryTest",
    srcs = ["StrategyParameterTypeRegistryTest.kt"],
    test_class = "com.verlumen.tradestream.strategies.StrategyParameterTypeRegistryTest",
    deps = [
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_parameter_type_registry",
        "//src/main/java/com/verlumen/tradestream/strategies:strategy_specs",
        "//third_party/java:gson",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:test_parameter_injector",
    ],
)
