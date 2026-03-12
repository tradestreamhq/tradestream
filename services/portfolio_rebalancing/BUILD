load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "rebalancer_lib",
    srcs = ["rebalancer.py"],
)

py_library(
    name = "scheduler_lib",
    srcs = ["scheduler.py"],
)

py_library(
    name = "service_lib",
    srcs = ["service.py"],
    deps = [
        ":rebalancer_lib",
        "//third_party/python:absl_py",
        "//third_party/python:asyncpg",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":rebalancer_lib",
        ":scheduler_lib",
        ":service_lib",
        "//third_party/python:absl_py",
        "//third_party/python:asyncpg",
    ],
)

# --- Test Targets ---
py_test(
    name = "rebalancer_test",
    srcs = ["rebalancer_test.py"],
    deps = [
        ":rebalancer_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "scheduler_test",
    srcs = ["scheduler_test.py"],
    deps = [
        ":scheduler_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "service_test",
    srcs = ["service_test.py"],
    deps = [
        ":rebalancer_lib",
        ":service_lib",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
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
    entrypoint = ["/services/portfolio_rebalancing/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/portfolio_rebalancing",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_portfolio_rebalancing_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/portfolio-rebalancing",
)

oci_load(
    name = "load_portfolio_rebalancing_image",
    image = ":image",
    repo_tags = ["portfolio-rebalancing:latest"],
)

filegroup(
    name = "portfolio_rebalancing_tarball",
    srcs = [":load_portfolio_rebalancing_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
