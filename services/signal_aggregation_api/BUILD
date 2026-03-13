load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")

py_library(
    name = "signal_aggregation_api_lib",
    srcs = ["main.py"],
    deps = [
        "//services/shared:auth",
        "//third_party/python:absl_py",
        "//third_party/python:flask",
        "//third_party/python:flask_cors",
        "//third_party/python:psycopg2_binary",
    ],
)

py_binary(
    name = "signal_aggregation_api",
    srcs = ["main.py"],
    main = "main.py",
    deps = [":signal_aggregation_api_lib"],
)

py_test(
    name = "signal_aggregation_api_test",
    size = "medium",
    timeout = "short",
    srcs = ["main_test.py"],
    main = "main_test.py",
    python_version = "PY3",
    deps = [
        ":signal_aggregation_api_lib",
        "//third_party/python:absl_py",
        "//third_party/python:flask",
        "//third_party/python:flask_cors",
        "//third_party/python:psycopg2_binary",
    ],
)

# --- OCI Image Rules ---
py_image_layer(
    name = "layers",
    binary = ":signal_aggregation_api",
)

oci_image(
    name = "image",
    base = "@python_3_13_slim",
    entrypoint = ["/services/signal_aggregation_api/signal_aggregation_api"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/signal_aggregation_api",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_signal_aggregation_api_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/signal-aggregation-api",
)

oci_load(
    name = "load_signal_aggregation_api_image",
    image = ":image",
    repo_tags = ["signal-aggregation-api:latest"],
)

filegroup(
    name = "signal_aggregation_api_tarball",
    srcs = [":load_signal_aggregation_api_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
