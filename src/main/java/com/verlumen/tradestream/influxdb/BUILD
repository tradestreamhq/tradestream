"""Build rules for InfluxDB components."""

load("@rules_java//java:defs.bzl", "java_library")

java_library(
    name = "influx_db_module",
    srcs = ["InfluxDbModule.java"],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/java:auto_value",
        "//third_party/java:guice",
        "//third_party/java:influxdb_client_java",
    ],
)
