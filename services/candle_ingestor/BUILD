load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "ingestion_helpers_lib",
    srcs = ["ingestion_helpers.py"],
    deps = [
        "//third_party:absl_py",
    ],
)

py_library(
    name = "cmc_client_lib",
    srcs = ["cmc_client.py"],
    deps = [
        "//third_party:absl_py",
        "//third_party:requests",
    ],
)

py_library(
    name = "tiingo_client_lib",
    srcs = ["tiingo_client.py"],
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

# Main application binary
py_binary(
    name = "main_app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":cmc_client_lib",
        ":influx_client_lib",
        ":tiingo_client_lib",
        ":ingestion_helpers_lib",
        "//third_party:absl_py",
    ],
)

# --- Test Targets ---
py_test(
    name = "ingestion_helpers_test",
    srcs = ["ingestion_helpers_test.py"],
    deps = [
        ":ingestion_helpers_lib",
    ],
)

py_test(
    name = "cmc_client_test",
    srcs = ["cmc_client_test.py"],
    deps = [
        ":cmc_client_lib",
        "//third_party:requests",
    ],
)

py_test(
    name = "tiingo_client_test",
    srcs = ["tiingo_client_test.py"],
    deps = [
        ":tiingo_client_lib",
        "//third_party:requests",
    ],
)

py_test(
    name = "influx_client_test",
    srcs = ["influx_client_test.py"],
    deps = [
        ":influx_client_lib",
    ],
)

py_test(
    name = "main_test", # New test target for main.py
    srcs = ["main_test.py"],
    deps = [
        ":main_app", # Depends on the main application code
        ":ingestion_helpers_lib",
        ":influx_client_lib", # For spec in mock
        ":tiingo_client_lib", # For patching
        "//third_party:absl_py", # For absltest and flagsaver
    ],
)
