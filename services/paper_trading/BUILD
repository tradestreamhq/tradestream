load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "postgres_client_lib",
    srcs = ["postgres_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:asyncpg",
    ],
)

py_library(
    name = "service_lib",
    srcs = ["service.py"],
    deps = [
        ":postgres_client_lib",
        "//services/shared:auth",
        "//services/shared:mcp_client",
        "//third_party/python:absl_py",
        "//third_party/python:flask",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "models_lib",
    srcs = ["models.py"],
    deps = [
        "//third_party/python:pydantic",
    ],
)

py_library(
    name = "virtual_portfolio_lib",
    srcs = ["virtual_portfolio.py"],
    deps = [
        ":models_lib",
    ],
)

py_library(
    name = "simulator_lib",
    srcs = ["simulator.py"],
    deps = [
        ":models_lib",
        ":virtual_portfolio_lib",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":postgres_client_lib",
        ":service_lib",
        "//third_party/python:absl_py",
    ],
)

# --- Test Targets ---
py_test(
    name = "simulator_test",
    srcs = ["simulator_test.py"],
    deps = [
        ":models_lib",
        ":simulator_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "service_test",
    srcs = ["service_test.py"],
    deps = [
        ":service_lib",
        "//third_party/python:pytest",
        "//third_party/python:requests",
    ],
)

py_test(
    name = "postgres_client_test",
    srcs = ["postgres_client_test.py"],
    deps = [
        ":postgres_client_lib",
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
    entrypoint = ["/services/paper_trading/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/paper_trading",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_paper_trading_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/paper-trading",
)

oci_load(
    name = "load_paper_trading_image",
    image = ":image",
    repo_tags = ["paper-trading:latest"],
)

filegroup(
    name = "paper_trading_tarball",
    srcs = [":load_paper_trading_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
