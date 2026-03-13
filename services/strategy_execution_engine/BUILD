load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")

py_library(
    name = "models",
    srcs = ["models.py"],
)

py_library(
    name = "engine",
    srcs = ["engine.py"],
    deps = [
        ":models",
        "//third_party/python:pyyaml",
    ],
)

py_library(
    name = "strategy_execution_engine_lib",
    srcs = ["main.py"],
    deps = [
        ":engine",
        ":models",
        "//services/shared:auth",
        "//third_party/python:absl_py",
        "//third_party/python:flask",
        "//third_party/python:flask_cors",
        "//third_party/python:psycopg2_binary",
        "//third_party/python:pyyaml",
    ],
)

py_binary(
    name = "strategy_execution_engine",
    srcs = ["main.py"],
    main = "main.py",
    deps = [":strategy_execution_engine_lib"],
)

py_test(
    name = "strategy_execution_engine_test",
    size = "medium",
    timeout = "short",
    srcs = ["main_test.py"],
    main = "main_test.py",
    python_version = "PY3",
    deps = [
        ":engine",
        ":models",
        ":strategy_execution_engine_lib",
        "//third_party/python:absl_py",
        "//third_party/python:flask",
        "//third_party/python:flask_cors",
        "//third_party/python:psycopg2_binary",
        "//third_party/python:pyyaml",
    ],
)

# --- OCI Image Rules ---
py_image_layer(
    name = "layers",
    binary = ":strategy_execution_engine",
)

oci_image(
    name = "image",
    base = "@python_3_13_slim",
    entrypoint = ["/services/strategy_execution_engine/strategy_execution_engine"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/strategy_execution_engine",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_strategy_execution_engine_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/strategy-execution-engine",
)

oci_load(
    name = "load_strategy_execution_engine_image",
    image = ":image",
    repo_tags = ["strategy-execution-engine:latest"],
)

filegroup(
    name = "strategy_execution_engine_tarball",
    srcs = [":load_strategy_execution_engine_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
