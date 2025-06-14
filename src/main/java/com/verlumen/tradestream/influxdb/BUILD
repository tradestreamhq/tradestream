"""Build rules for InfluxDB components."""

load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

package(default_visibility=["//visibility:public"])

kt_jvm_library(
    name = "influx_db_client_factory",
    srcs = ["InfluxDbClientFactory.kt"],
    deps = [
        "//third_party/java:influxdb_client_java",
    ],
)

kt_jvm_library(
    name = "influx_db_config",
    srcs = ["InfluxDbConfig.kt"],
)

kt_jvm_library(
    name = "influx_db_module",
    srcs = ["InfluxDbModule.kt"],
    deps = [
        "//third_party/java:guice",
        "//third_party/java:influxdb_client_java",
    ],
)
