load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")

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
        "//third_party:tenacity",  # Added
    ],
)

py_library(
    name = "tiingo_client_lib",
    srcs = ["tiingo_client.py"],
    deps = [
        "//third_party:absl_py",
        "//third_party:requests",
        "//third_party:tenacity",  # Added
    ],
)

py_library(
    name = "influx_client_lib",
    srcs = ["influx_client.py"],
    deps = [
        "//third_party:absl_py",
        "//third_party:influxdb_client",
        "//third_party:tenacity",  # Added
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

# --- OCI Image Rules ---
py_image_layer(
    name = "main_app_py_layers",
    binary = ":main_app",
    # package_dir = "/app", # Default is often /app/<binary_name_target>
)

oci_image(
    name = "candle_ingestor_image_amd64",
    base = "@python_3_13_slim_bullseye_for_ingestor//image",
    architecture = "amd64",
    os = "linux",
    entrypoint = ["/app/main_app/main_app"], # Adjusted based on typical py_image_layer structure
    tars = [":main_app_py_layers"],
)

oci_image(
    name = "candle_ingestor_image_arm64",
    base = "@python_3_13_slim_bullseye_for_ingestor//image",
    architecture = "arm64",
    os = "linux",
    entrypoint = ["/app/main_app/main_app"], # Adjusted based on typical py_image_layer structure
    tars = [":main_app_py_layers"],
)

oci_image_index(
    name = "candle_ingestor_image_for_deployment",
    images = {
        "linux/amd64": ":candle_ingestor_image_amd64",
        "linux/arm64": ":candle_ingestor_image_arm64",
    },
    repo_tags = ["tradestreamhq/candle-ingestor:latest"],
)

oci_push(
    name = "push_candle_ingestor_image",
    image = ":candle_ingestor_image_for_deployment",
    repository = "tradestreamhq/candle-ingestor",
)
