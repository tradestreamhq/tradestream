load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = [
        "//src/test/java/com/verlumen/tradestream/discovery:__pkg__",
    ],)

kt_jvm_library(
    name = "discovery_module",
    srcs = ["DiscoveryModule.kt"],
    visibility = [
        "//src/main/java/com/verlumen/tradestream/pipeline:__pkg__",
    ],
    deps = [
        ":genotype_converter",
        ":genotype_converter_impl",
        ":param_config",
        ":param_config_manager",
        ":param_config_manager_impl",
        ":param_configs",
        "//third_party/java:guice",
    ],
)

java_library(
    name = "genotype_converter",
    srcs = ["GenotypeConverter.java"],
    visibility = [
        "//src/main/java/com/verlumen/tradestream/backtesting:__pkg__",
        "//src/test/java/com/verlumen/tradestream/backtesting:__pkg__",
        "//src/test/java/com/verlumen/tradestream/discovery:__pkg__",
    ],
    deps = [
        "//protos:strategies_java_proto",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "genotype_converter_impl",
    srcs = ["GenotypeConverterImpl.java"],
    deps = [
        ":genotype_converter",
        ":param_config",
        ":param_config_manager",
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "param_config",
    srcs = ["ParamConfig.java"],
    visibility = [
        "//src/main/java/com/verlumen/tradestream/backtesting:__subpackages__",
    ],
    deps = [
        "//protos:strategies_java_proto",
        "//src/main/java/com/verlumen/tradestream/backtesting:chromosome_spec",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:protobuf_java",
    ],
)

java_library(
    name = "param_config_manager",
    srcs = ["ParamConfigManager.java"],
    visibility = [
        "//src/main/java/com/verlumen/tradestream/backtesting:__pkg__",
    ],
    deps = [
        ":param_config",
        "//protos:strategies_java_proto",
    ],
)

java_library(
    name = "param_config_manager_impl",
    srcs = ["ParamConfigManagerImpl.java"],
    deps = [
        ":param_config",
        ":param_config_manager",
        "//protos:strategies_java_proto",
        "//third_party/java:guava",
        "//third_party/java:guice",
        "//third_party/java:mug",
    ],
)

java_library(
    name = "param_configs",
    srcs = [
        "ParamConfigs.java",
    ],
    deps = [
        ":param_config",
        "//src/main/java/com/verlumen/tradestream/backtesting/momentumoscillators:momentum_oscillator_params",
        "//src/main/java/com/verlumen/tradestream/backtesting/movingaverages:moving_average_params",
        "//src/main/java/com/verlumen/tradestream/backtesting/patternrecognition:pattern_recognition_params",
        "//src/main/java/com/verlumen/tradestream/backtesting/trendfollowing:trend_following_params",
        "//third_party/java:guava",
    ],
)
