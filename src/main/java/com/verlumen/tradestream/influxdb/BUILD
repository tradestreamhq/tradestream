"""Build rules for InfluxDB components."""

load("@rules_kotlin//kotlin:jvm.bzl", "kt_jvm_library")

kt_jvm_library(
    name = "influx_db_module",
    srcs = ["InfluxDbModule.kt"],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/java:auto_value",
        "//third_party/java:guice",
        "//third_party/java:influxdb_client_java",
    ],
)
