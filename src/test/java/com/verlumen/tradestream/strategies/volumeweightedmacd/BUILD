load("@rules_java//java:defs.bzl", "java_test")

java_test(
    name = "param_config_test",
    srcs = ["VolumeWeightedMacdParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.volumeweightedmacd.VolumeWeightedMacdParamConfigTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/volumeweightedmacd:param_config",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["VolumeWeightedMacdStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.volumeweightedmacd.VolumeWeightedMacdStrategyFactoryTest",
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/volumeweightedmacd:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:ta4j_core",
    ],
)