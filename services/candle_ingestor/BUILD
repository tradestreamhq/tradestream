load("@rules_python//python:py_binary.bzl", "py_binary")

py_binary(
    name = "main",
    srcs = ["main.py"],
    deps = [
        "//third_party:absl_py",
        "//third_party:influxdb_client",
        "//third_party:requests",
    ],
)
