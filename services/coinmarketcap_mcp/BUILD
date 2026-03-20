load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "cmc_client_lib",
    srcs = ["cmc_client.py"],
    deps = [
        "//third_party/python:httpx",
    ],
)

py_library(
    name = "server_lib",
    srcs = ["server.py"],
    deps = [
        ":cmc_client_lib",
        "//services/shared:mcp_cache",
        "//services/shared:mcp_errors",
        "//services/shared:mcp_metadata",
        "//third_party/python:mcp",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":cmc_client_lib",
        ":server_lib",
        "//services/shared:auth",
        "//third_party/python:absl_py",
        "//third_party/python:mcp",
    ],
)

# --- Test Targets ---
py_test(
    name = "cmc_client_test",
    srcs = ["cmc_client_test.py"],
    deps = [
        ":cmc_client_lib",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_test(
    name = "server_test",
    srcs = ["server_test.py"],
    deps = [
        ":cmc_client_lib",
        ":server_lib",
        "//third_party/python:mcp",
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
    entrypoint = ["/services/coinmarketcap_mcp/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/coinmarketcap_mcp",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_coinmarketcap_mcp_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/coinmarketcap-mcp",
)

oci_load(
    name = "load_coinmarketcap_mcp_image",
    image = ":image",
    repo_tags = ["coinmarketcap-mcp:latest"],
)

filegroup(
    name = "coinmarketcap_mcp_tarball",
    srcs = [":load_coinmarketcap_mcp_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
