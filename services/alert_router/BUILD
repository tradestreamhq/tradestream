load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "config_lib",
    srcs = ["config.py"],
)

py_library(
    name = "models_lib",
    srcs = ["models.py"],
)

py_library(
    name = "channels_lib",
    srcs = ["channels.py"],
    deps = [
        ":models_lib",
        "//third_party/python:absl_py",
        "//third_party/python:requests",
        "//third_party/python:tenacity",
    ],
)

py_library(
    name = "router_lib",
    srcs = ["router.py"],
    deps = [
        ":channels_lib",
        ":models_lib",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "app_lib",
    srcs = ["app.py"],
    deps = [
        ":models_lib",
        ":router_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:pagination",
        "//services/rest_api_shared:responses",
        "//third_party/python:fastapi",
    ],
)

py_library(
    name = "main_lib",
    srcs = ["main.py"],
    deps = [
        ":app_lib",
        ":config_lib",
        "//third_party/python:uvicorn",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":main_lib",
    ],
)

py_test(
    name = "alert_router_test",
    srcs = ["alert_router_test.py"],
    deps = [
        ":app_lib",
        ":channels_lib",
        ":models_lib",
        ":router_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
        "//third_party/python:requests",
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
    entrypoint = ["/services/alert_router/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/alert_router",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_alert_router_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/alert-router",
)

oci_load(
    name = "load_alert_router_image",
    image = ":image",
    repo_tags = ["alert-router:latest"],
)

filegroup(
    name = "alert_router_tarball",
    srcs = [":load_alert_router_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
