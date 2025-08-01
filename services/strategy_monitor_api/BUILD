load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push", "oci_load")
load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")

py_library(
    name = "strategy_monitor_api_lib",
    srcs = ["main.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:flask",
        "//third_party/python:flask_cors",
        "//third_party/python:psycopg2_binary",
    ],
)

py_binary(
    name = "strategy_monitor_api",
    srcs = ["main.py"],
    main = "main.py",
    deps = [":strategy_monitor_api_lib"],
)

py_test(
    name = "strategy_monitor_api_test",
    size = "medium",
    timeout = "short",
    srcs = ["main_test.py"],
    main = "main_test.py",
    python_version = "PY3",
    deps = [
        ":strategy_monitor_api_lib",
        "//third_party/python:absl_py",
        "//third_party/python:flask",
        "//third_party/python:flask_cors",
        "//third_party/python:psycopg2_binary",
    ],
)

# --- OCI Image Rules ---
py_image_layer(
    name = "layers",
    binary = ":strategy_monitor_api",
)

oci_image(
    name = "image",
    base = "@python_3_13_slim",
    entrypoint = ["/services/strategy_monitor_api/strategy_monitor_api"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/strategy_monitor_api",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_strategy_monitor_api_image",
    image = ":images",
    repository = "tradestreamhq/strategy-monitor-api",
)

oci_load(
    name = "load_strategy_monitor_api_image",
    image = ":image",
    repo_tags = ["strategy-monitor-api:latest"],
)

filegroup(
    name = "strategy_monitor_api_tarball",
    srcs = [":load_strategy_monitor_api_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
