load("@rules_java//java:defs.bzl", "java_library")
load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility = ["//visibility:public"])

java_library(
    name = "bar_series_builder",
    srcs = ["BarSeriesBuilder.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:guava",
        "//third_party/java:protobuf_java",
        "//third_party/java:protobuf_java_util",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "bar_series_factory",
    srcs = ["BarSeriesFactory.java"],
    deps = [
        "//protos:marketdata_java_proto",
        "//third_party/java:guava",
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "trix_indicator",
    srcs = ["TRIXIndicator.java"],
    deps = [
        "//third_party/java:ta4j_core",
    ],
)

kt_jvm_library(
    name = "momentum_indicator",
    srcs = ["MomentumIndicator.kt"],
    deps = [
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "rvi_indicator",
    srcs = ["RviIndicator.java"],
    deps = [
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "volume_weighted_macd_line_indicator",
    srcs = ["VolumeWeightedMacdLineIndicator.java"],
    deps = [
        "//third_party/java:ta4j_core",
    ],
)

java_library(
    name = "ta4j_module",
    srcs = ["Ta4jModule.java"],
    deps = [
        ":bar_series_builder",
        ":bar_series_factory",
        ":momentum_indicator",
        ":rvi_indicator",
        ":trix_indicator",
        ":volume_weighted_macd_line_indicator",
        "//third_party/java:guice",
    ],
)

java_library(
    name = "test_bar_series_builder",
    srcs = ["TestBarSeriesBuilder.java"],
    deps = [
        "//third_party/java:ta4j_core",
    ],
)
