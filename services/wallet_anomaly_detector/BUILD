# --- OCI Image Rules ---
load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "wallet_anomaly_detector_lib",
    srcs = ["main.py"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":wallet_anomaly_detector_lib",
    ],
)

# Unit Tests
py_test(
    name = "main_test",
    srcs = [
        "conftest.py",
        "main_test.py",
    ],
    deps = [
        ":wallet_anomaly_detector_lib",
        "//third_party/python:absl_py",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_image_layer(
    name = "layers",
    binary = ":app",
)

oci_image(
    name = "image",
    base = "@python_3_13_slim",
    entrypoint = ["/services/wallet_anomaly_detector/app"],
    tars = [":layers"],
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_wallet_anomaly_detector_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/wallet-anomaly-detector",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
