java_test(
    name = "param_config_test",
    srcs = ["VolumeProfileParamConfigTest.java"],
    test_class = "com.verlumen.tradestream.strategies.volumeprofile.VolumeProfileParamConfigTest",
    visibility = ["//visibility:public"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/volumeprofile:param_config",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:protobuf_java",
        "//third_party/java:truth",
    ],
)

java_test(
    name = "strategy_factory_test",
    srcs = ["VolumeProfileStrategyFactoryTest.java"],
    test_class = "com.verlumen.tradestream.strategies.volumeprofile.VolumeProfileStrategyFactoryTest",
    visibility = ["//visibility:public"],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/strategies/volumeprofile:strategy_factory",
        "//third_party/java:junit",
        "//third_party/java:ta4j_core",
        "//third_party/java:truth",
    ],
)
