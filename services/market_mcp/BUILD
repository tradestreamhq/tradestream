load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "influxdb_client_lib",
    visibility = ["//visibility:public"],
    srcs = ["influxdb_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:influxdb_client",
    ],
)

py_library(
    name = "redis_client_lib",
    visibility = ["//visibility:public"],
    srcs = ["redis_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:redis",
    ],
)

py_library(
    name = "server_lib",
    srcs = ["server.py"],
    deps = [
        ":influxdb_client_lib",
        ":redis_client_lib",
        "//third_party/python:mcp",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":influxdb_client_lib",
        ":redis_client_lib",
        ":server_lib",
        "//services/shared:auth",
        "//third_party/python:absl_py",
        "//third_party/python:mcp",
    ],
)

# --- Test Targets ---
py_test(
    name = "server_test",
    srcs = ["server_test.py"],
    args = [
        "--influxdb_url=http://localhost:8086",
        "--influxdb_token=test-token",
        "--influxdb_org=tradestream-org",
        "--influxdb_bucket=tradestream-data",
        "--redis_host=localhost",
        "--redis_port=6379",
    ],
    deps = [
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
    entrypoint = ["/services/market_mcp/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/market_mcp",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_market_mcp_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/market-mcp",
)

oci_load(
    name = "load_market_mcp_image",
    image = ":image",
    repo_tags = ["market-mcp:latest"],
)

filegroup(
    name = "market_mcp_tarball",
    srcs = [":load_market_mcp_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
