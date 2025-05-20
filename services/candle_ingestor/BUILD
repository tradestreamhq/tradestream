load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_push")

py_library(
    name = "ingestion_helpers_lib",
    srcs = ["ingestion_helpers.py"],
    deps = [
        "//third_party:absl_py",
    ],
)

# --- OCI Image Rules ---

oci_image(
    name = "candle_ingestor_image",
    base = "@python_base_image_for_ingestor//image",
    entrypoint = ["/app/main_app"], # Assumes main_app is the launcher script
    files = [":main_app"],  # Use files attribute with py_binary
    package_dir = "/app",   # Specify where py_binary output goes in the image
    # Environment variables and cmd will be set by Kubernetes, not here.
)

oci_push(
    name = "push_candle_ingestor_image",
    image = ":candle_ingestor_image",
    repository = "your-docker-registry/candle-ingestor",  # Placeholder
    remote_tags = ["latest"],  # Placeholder
)

py_library(
    name = "cmc_client_lib",
    srcs = ["cmc_client.py"],
    deps = [
        "//third_party:absl_py",
        "//third_party:requests",
        "@pypi_tenacity//:pkg",
    ],
)

py_library(
    name = "tiingo_client_lib",
    srcs = ["tiingo_client.py"],
    deps = [
        "//third_party:absl_py",
        "//third_party:requests",
        "@pypi_tenacity//:pkg",
    ],
)

py_library(
    name = "influx_client_lib",
    srcs = ["influx_client.py"],
    deps = [
        "//third_party:absl_py",
        "//third_party:influxdb_client",
        "@pypi_tenacity//:pkg",
    ],
)

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
    name = "main_test",
    srcs = ["main_test.py"],
    # Add dummy arguments for required flags:
    args = [
        "--cmc_api_key=dummy_cmc_key_for_test",
        "--tiingo_api_key=dummy_tiingo_key_for_test",
        "--influxdb_token=dummy_influx_token_for_test",
        "--influxdb_org=dummy_influx_org_for_test",
        # You can also override other flags if needed for testing defaults
        # e.g., "--influxdb_url=http://mock-influx:8086",
    ],
    deps = [
        ":main_app",
        ":ingestion_helpers_lib",
        ":influx_client_lib", 
        ":tiingo_client_lib",
        "//third_party:absl_py",
    ],
)
