load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_push", "oci_tarball")
load("@aspect_bazel_lib//lib:tar.bzl", "tar")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "indicator_registry",
    srcs = ["indicator_registry.py"],
    deps = [
        "@pypi//vectorbt",
        "@pypi//pandas",
        "@pypi//numpy",
    ],
)

py_library(
    name = "vectorbt_runner",
    srcs = ["vectorbt_runner.py"],
    deps = [
        ":indicator_registry",
        "@pypi//vectorbt",
        "@pypi//pandas",
        "@pypi//numpy",
    ],
)

py_library(
    name = "backtesting_service",
    srcs = ["backtesting_service.py"],
    deps = [
        ":vectorbt_runner",
        "@pypi//grpcio",
    ],
)

py_binary(
    name = "main",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":backtesting_service",
    ],
)

py_test(
    name = "test_vectorbt_runner",
    srcs = ["tests/test_vectorbt_runner.py"],
    deps = [
        ":vectorbt_runner",
        ":indicator_registry",
        "@pypi//pytest",
    ],
    size = "medium",
)

# Container image
tar(
    name = "app_layer",
    srcs = [
        "indicator_registry.py",
        "vectorbt_runner.py",
        "backtesting_service.py",
        "main.py",
        "requirements.txt",
    ],
)

oci_image(
    name = "image",
    base = "@python_3_13_slim",
    tars = [":app_layer"],
    entrypoint = ["python", "/app/main.py"],
    cmd = ["--port", "8080"],
    exposed_ports = ["8080/tcp", "50051/tcp"],
)

oci_tarball(
    name = "tarball",
    image = ":image",
    repo_tags = ["tradestream/backtesting:latest"],
)
