load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "redis_client_lib",
    srcs = ["redis_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:redis",
    ],
)

py_library(
    name = "postgres_client_lib",
    srcs = ["postgres_client.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:asyncpg",
    ],
)

py_library(
    name = "server_lib",
    srcs = ["server.py"],
    deps = [
        ":postgres_client_lib",
        ":redis_client_lib",
        "//third_party/python:mcp",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":postgres_client_lib",
        ":redis_client_lib",
        ":server_lib",
        "//services/shared:config",
        "//third_party/python:absl_py",
        "//third_party/python:mcp",
    ],
)

# --- Test Targets ---
py_test(
    name = "server_test",
    srcs = ["server_test.py"],
    args = [
        "--postgres_host=localhost",
        "--postgres_port=5432",
        "--postgres_database=tradestream",
        "--postgres_username=test_user",
        "--postgres_password=test_password",
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
    entrypoint = ["/services/signal_mcp/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/signal_mcp",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_signal_mcp_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/signal-mcp",
)

oci_load(
    name = "load_signal_mcp_image",
    image = ":image",
    repo_tags = ["signal-mcp:latest"],
)

filegroup(
    name = "signal_mcp_tarball",
    srcs = [":load_signal_mcp_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
