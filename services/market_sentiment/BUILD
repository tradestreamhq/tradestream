load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "aggregator_lib",
    srcs = ["aggregator.py"],
    deps = [
        "//third_party/python:httpx",
    ],
)

py_library(
    name = "signal_generator_lib",
    srcs = ["signal_generator.py"],
    deps = [
        ":aggregator_lib",
    ],
)

py_library(
    name = "app_lib",
    srcs = ["app.py"],
    deps = [
        ":aggregator_lib",
        ":signal_generator_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:responses",
        "//third_party/python:fastapi",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":aggregator_lib",
        ":app_lib",
        ":signal_generator_lib",
        "//services/shared:structured_logger",
        "//third_party/python:absl_py",
        "//third_party/python:uvicorn",
    ],
)

py_test(
    name = "aggregator_test",
    srcs = ["aggregator_test.py"],
    deps = [
        ":aggregator_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "signal_generator_test",
    srcs = ["signal_generator_test.py"],
    deps = [
        ":aggregator_lib",
        ":signal_generator_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "app_test",
    srcs = ["app_test.py"],
    deps = [
        ":aggregator_lib",
        ":app_lib",
        ":signal_generator_lib",
        "//third_party/python:fastapi",
        "//third_party/python:httpx",
        "//third_party/python:pytest",
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
    entrypoint = ["/services/market_sentiment/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/market_sentiment",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_market_sentiment_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/market-sentiment",
)

oci_load(
    name = "load_market_sentiment_image",
    image = ":image",
    repo_tags = ["market-sentiment:latest"],
)

filegroup(
    name = "market_sentiment_tarball",
    srcs = [":load_market_sentiment_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
