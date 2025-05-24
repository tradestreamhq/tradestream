load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
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
        "//third_party:tenacity",
    ],
)

py_library(
    name = "tiingo_client_lib",
    srcs = ["tiingo_client.py"],
    deps = [
        "//third_party:absl_py",
        "//third_party:requests",
        "//third_party:tenacity",
    ],
)

py_library(
    name = "influx_client_lib",
    srcs = ["influx_client.py"],
    deps = [
        "//third_party:absl_py",
        "//third_party:influxdb_client",
        "//third_party:tenacity",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":cmc_client_lib",
        ":influx_client_lib",
        ":ingestion_helpers_lib",
        ":tiingo_client_lib",
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
        ":app",
        ":influx_client_lib",
        ":ingestion_helpers_lib",
        ":tiingo_client_lib",
        "//third_party:absl_py",
    ],
)

# --- OCI Image Rules ---
py_image_layer(
    name = "layers",
    binary = ":app",
    # package_dir = "/app", # Default is often /app/<binary_name_target>
)

oci_image(
    name = "image",
    base = "@python_3_13_slim",
    entrypoint = ["/services/candle_ingestor/app"],
    tars = [":layers"],
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_candle_ingestor_image",
    image = ":images",
    repository = "tradestreamhq/candle-ingestor",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
