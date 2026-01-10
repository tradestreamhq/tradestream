load("@aspect_bazel_lib//lib:tar.bzl", "tar")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_push", "oci_tarball")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "indicator_registry",
    srcs = ["indicator_registry.py"],
    deps = [
        "@pypi//numpy",
        "@pypi//pandas",
        "@pypi//vectorbt",
    ],
)

py_library(
    name = "vectorbt_runner",
    srcs = ["vectorbt_runner.py"],
    deps = [
        ":indicator_registry",
        "@pypi//numpy",
        "@pypi//pandas",
        "@pypi//vectorbt",
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
    size = "medium",
    srcs = ["tests/test_vectorbt_runner.py"],
    deps = [
        ":indicator_registry",
        ":vectorbt_runner",
        "@pypi//pytest",
    ],
)

# Container image
tar(
    name = "app_layer",
    srcs = [
        "backtesting_service.py",
        "indicator_registry.py",
        "main.py",
        "requirements.txt",
        "vectorbt_runner.py",
    ],
)

oci_image(
    name = "image",
    base = "@python_3_13_slim",
    cmd = [
        "--port",
        "8080",
    ],
    entrypoint = [
        "python",
        "/app/main.py",
    ],
    exposed_ports = [
        "8080/tcp",
        "50051/tcp",
    ],
    tars = [":app_layer"],
)

oci_tarball(
    name = "tarball",
    image = ":image",
    repo_tags = ["tradestream/backtesting:latest"],
)
