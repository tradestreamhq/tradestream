load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "polymarket_client_lib",
    srcs = ["polymarket_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
    ],
)

py_library(
    name = "kalshi_client_lib",
    srcs = ["kalshi_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
    ],
)

py_library(
    name = "signal_generator_lib",
    srcs = ["signal_generator.py"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "insider_detector_lib",
    srcs = ["insider_detector.py"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "correlation_tracker_lib",
    srcs = ["correlation_tracker.py"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "prediction_market_provider_lib",
    srcs = ["prediction_market_provider.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":kalshi_client_lib",
        ":polymarket_client_lib",
        "//shared/marketdata:provider_lib",
        "//third_party/python:absl_py",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":correlation_tracker_lib",
        ":insider_detector_lib",
        ":kalshi_client_lib",
        ":polymarket_client_lib",
        ":signal_generator_lib",
        "//third_party/python:absl_py",
    ],
)

# --- Test Targets ---
py_test(
    name = "polymarket_client_test",
    srcs = ["polymarket_client_test.py"],
    deps = [
        ":polymarket_client_lib",
        "//third_party/python:requests",
    ],
)

py_test(
    name = "kalshi_client_test",
    srcs = ["kalshi_client_test.py"],
    deps = [
        ":kalshi_client_lib",
        "//third_party/python:requests",
    ],
)

py_test(
    name = "signal_generator_test",
    srcs = ["signal_generator_test.py"],
    deps = [
        ":signal_generator_lib",
    ],
)

py_test(
    name = "insider_detector_test",
    srcs = ["insider_detector_test.py"],
    deps = [
        ":insider_detector_lib",
    ],
)

py_test(
    name = "correlation_tracker_test",
    srcs = ["correlation_tracker_test.py"],
    deps = [
        ":correlation_tracker_lib",
    ],
)

py_test(
    name = "main_test",
    srcs = ["main_test.py"],
    args = [
        "--run_mode=dry",
        "--polymarket_api_url=http://localhost:8080",
        "--kalshi_enabled=false",
    ],
    deps = [
        ":app",
        ":correlation_tracker_lib",
        ":insider_detector_lib",
        ":kalshi_client_lib",
        ":polymarket_client_lib",
        ":signal_generator_lib",
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
    entrypoint = ["/services/prediction_markets/app"],
    tars = [":layers"],
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_prediction_markets_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/prediction-markets",
)

oci_load(
    name = "load_prediction_markets_image",
    image = ":image",
    repo_tags = ["prediction-markets:latest"],
)

filegroup(
    name = "prediction_markets_tarball",
    srcs = [":load_prediction_markets_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
