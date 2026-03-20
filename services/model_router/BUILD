load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "model_registry",
    srcs = [
        "__init__.py",
        "model_registry.py",
    ],
)

py_library(
    name = "router",
    srcs = [
        "__init__.py",
        "router.py",
    ],
    deps = [
        ":model_registry",
    ],
)

py_library(
    name = "cost_tracker",
    srcs = [
        "__init__.py",
        "cost_tracker.py",
    ],
    deps = [
        ":model_registry",
    ],
)

py_library(
    name = "budget_enforcer",
    srcs = [
        "__init__.py",
        "budget_enforcer.py",
    ],
)

py_library(
    name = "model_router_lib",
    srcs = [
        "__init__.py",
        "gateway.py",
    ],
    deps = [
        ":budget_enforcer",
        ":cost_tracker",
        ":model_registry",
        ":router",
        "//third_party/python:fastapi",
        "//third_party/python:pydantic",
        "//third_party/python:uvicorn",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":model_router_lib",
    ],
)

# --- Tests ---

py_test(
    name = "model_registry_test",
    srcs = [
        "conftest.py",
        "model_registry_test.py",
    ],
    deps = [
        ":model_registry",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "router_test",
    srcs = [
        "conftest.py",
        "router_test.py",
    ],
    deps = [
        ":router",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_test(
    name = "cost_tracker_test",
    srcs = [
        "conftest.py",
        "cost_tracker_test.py",
    ],
    deps = [
        ":cost_tracker",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "budget_enforcer_test",
    srcs = [
        "conftest.py",
        "budget_enforcer_test.py",
    ],
    deps = [
        ":budget_enforcer",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "gateway_test",
    srcs = [
        "conftest.py",
        "gateway_test.py",
    ],
    deps = [
        ":model_router_lib",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
    ],
)

# --- OCI Image ---

py_image_layer(
    name = "layers",
    binary = ":app",
)

oci_image(
    name = "image",
    base = "@python_3_13_slim",
    entrypoint = ["/services/model_router/app"],
    tars = [":layers"],
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_model_router_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/model-router",
)

oci_load(
    name = "load_model_router_image",
    image = ":image",
    repo_tags = ["model-router:latest"],
)

filegroup(
    name = "model_router_tarball",
    srcs = [":load_model_router_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
