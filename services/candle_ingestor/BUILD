load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")

py_library(
    name = "cmc_client_lib",
    srcs = ["cmc_client.py"],
    deps = [
        "//third_party:absl_py",
        "//third_party:requests",
    ],
)

py_library(
    name = "influx_client_lib",
    srcs = ["influx_client.py"],
    deps = [
        "//third_party:absl_py",
        "//third_party:influxdb_client",
    ],
)

py_binary(
    name = "main",
    srcs = ["main.py"],
    main = "main.py", # Explicitly set main
    deps = [
        ":cmc_client_lib",
        ":influx_client_lib",
        "//third_party:absl_py",
        "//third_party:influxdb_client",
        "//third_party:requests",
    ],
)
