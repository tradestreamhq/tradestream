load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "models_lib",
    srcs = [
        "__init__.py",
        "models.py",
    ],
    deps = [
        "//third_party/python:pydantic",
    ],
)

py_library(
    name = "dispatcher_lib",
    srcs = [
        "__init__.py",
        "dispatcher.py",
    ],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:asyncpg",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
    ],
)

py_library(
    name = "app_lib",
    srcs = [
        "__init__.py",
        "app.py",
    ],
    deps = [
        ":dispatcher_lib",
        ":models_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:responses",
        "//services/shared:auth",
        "//third_party/python:asyncpg",
        "//third_party/python:fastapi",
        "//third_party/python:pydantic",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":app_lib",
        "//third_party/python:asyncpg",
        "//third_party/python:uvicorn",
    ],
)

py_test(
    name = "app_test",
    srcs = ["app_test.py"],
    deps = [
        ":app_lib",
        ":dispatcher_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
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
    entrypoint = ["/services/webhook_api/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/webhook_api",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_webhook_api_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/webhook-api",
)

oci_load(
    name = "load_webhook_api_image",
    image = ":image",
    repo_tags = ["webhook-api:latest"],
)

filegroup(
    name = "webhook_api_tarball",
    srcs = [":load_webhook_api_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
