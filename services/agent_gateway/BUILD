# --- OCI Image Rules ---
load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "agent_gateway_lib",
    srcs = ["main.py"],
    deps = [
        "//third_party/python:asyncpg",
        "//third_party/python:fastapi",
        "//third_party/python:redis",
        "//third_party/python:sse_starlette",
        "//third_party/python:uvicorn",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":agent_gateway_lib",
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
        ":agent_gateway_lib",
        "//third_party/python:httpx",
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
    entrypoint = ["/services/agent_gateway/app"],
    tars = [":layers"],
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_agent_gateway_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/agent-gateway",
)

oci_load(
    name = "load_agent_gateway_image",
    image = ":image",
    repo_tags = ["agent-gateway:latest"],
)

filegroup(
    name = "agent_gateway_tarball",
    srcs = [":load_agent_gateway_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
