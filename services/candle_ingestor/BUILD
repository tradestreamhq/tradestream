load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")
load("@rules_python//python:pip.bzl", "pip_parse")

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
    main = "main.py",
    deps = [
        ":cmc_client_lib",
        ":influx_client_lib",
        "//third_party:absl_py",
    ],
)

# --- Test Targets ---
py_test(
    name = "cmc_client_test",
    srcs = ["cmc_client_test.py"],
    deps = [
        ":cmc_client_lib",
        "//third_party:requests",
    ],
)

py_test(
    name = "influx_client_test",
    srcs = ["influx_client_test.py"],
    python_version = "PY3",
    deps = [
        ":influx_client_lib",
        "//third_party:influxdb_client", 
    ],
)
