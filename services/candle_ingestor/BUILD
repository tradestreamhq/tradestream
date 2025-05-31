# services/candle_ingestor/BUILD
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
        "//third_party/python:absl_py",
    ],
)

# New CCXT client library
py_library(
    name = "ccxt_client_lib",
    srcs = ["ccxt_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:ccxt",
        "//third_party/python:tenacity",
    ],
)

# Keep tiingo_client_lib for backward compatibility if needed
py_library(
    name = "tiingo_client_lib",
    srcs = ["tiingo_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
    ],
)

py_library(
    name = "influx_client_lib",
    srcs = ["influx_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:influxdb_client",
        "//third_party/python:tenacity",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":ccxt_client_lib",  # Updated to use CCXT client
        ":influx_client_lib",
        ":ingestion_helpers_lib",
        "//shared/cryptoclient:redis_crypto_client_lib",
        "//shared/persistence:influxdb_last_processed_tracker_lib",
        "//third_party/python:absl_py",
        "//third_party/python:redis",
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
    name = "ccxt_client_test",
    srcs = ["ccxt_client_test.py"],
    deps = [
        ":ccxt_client_lib",
        "//third_party/python:ccxt",
    ],
)

py_test(
    name = "tiingo_client_test",
    srcs = ["tiingo_client_test.py"],
    deps = [
        ":tiingo_client_lib",
        "//third_party/python:requests",
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
    args = [
        "--influxdb_token=dummy_influx_token_for_test",
        "--influxdb_org=dummy_influx_org_for_test",
        "--redis_host=mock_redis_host_for_test",
        "--redis_key_crypto_symbols=test_crypto_symbols_key",
        "--exchanges=binance",
    ],
    deps = [
        ":app",
        ":ccxt_client_lib",
        ":influx_client_lib",
        ":ingestion_helpers_lib",
        "//shared/cryptoclient:redis_crypto_client_lib",
        "//shared/persistence:influxdb_last_processed_tracker_lib",
        "//third_party/python:absl_py",
        "//third_party/python:redis",
    ],
)

py_test(
    name = "symbol_validation_test",
    srcs = ["symbol_validation_test.py"],
    deps = [
        ":app",  # For the validation functions
        "//third_party/python:absl_py",
    ],
)

# --- OCI Image Rules ---
py_image_layer(
    name = "layers",
    binary = ":app",
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
