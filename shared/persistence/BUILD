load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "influxdb_last_processed_tracker_lib",
    srcs = ["influxdb_last_processed_tracker.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:influxdb_client",
        "//third_party/python:tenacity",
    ],
)

py_test(
    name = "influxdb_last_processed_tracker_test",
    srcs = ["influxdb_last_processed_tracker_test.py"],
    deps = [
        ":influxdb_last_processed_tracker_lib",
        "//third_party/python:absl_py",
        "//third_party/python:influxdb_client",
        "//third_party/python:tenacity",
    ],
)
