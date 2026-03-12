load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "indicator_registry_lib",
    srcs = ["indicator_registry.py"],
    deps = [
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:vectorbt",
    ],
)

py_library(
    name = "vectorbt_runner_lib",
    srcs = ["vectorbt_runner.py"],
    deps = [
        ":indicator_registry_lib",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:vectorbt",
    ],
)

py_library(
    name = "yaml_strategy_loader_lib",
    srcs = ["yaml_strategy_loader.py"],
    deps = [
        ":indicator_registry_lib",
        "//third_party/python:pandas",
        "//third_party/python:pyyaml",
    ],
)

py_library(
    name = "backtesting_service_lib",
    srcs = ["backtesting_service.py"],
    deps = [
        ":vectorbt_runner_lib",
        "//protos:backtesting_py_proto",
        "//protos:marketdata_py_proto",
        "//protos:strategies_py_proto",
        "//services/shared:strategy_parameter_registry",
        "//third_party/python:grpcio",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
    ],
)

py_library(
    name = "engine_lib",
    srcs = ["engine.py"],
    deps = [
        "//third_party/python:numpy",
        "//third_party/python:pandas",
    ],
)

py_library(
    name = "app_lib",
    srcs = ["app.py"],
    deps = [
        ":engine_lib",
        ":vectorbt_runner_lib",
        "//services/rest_api_shared:health",
        "//services/rest_api_shared:pagination",
        "//services/rest_api_shared:responses",
        "//services/shared:auth",
        "//third_party/python:asyncpg",
        "//third_party/python:fastapi",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:pydantic",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":backtesting_service_lib",
        "//third_party/python:grpcio",
    ],
)

py_test(
    name = "test_vectorbt_runner",
    size = "medium",
    srcs = ["tests/test_vectorbt_runner.py"],
    deps = [
        ":indicator_registry_lib",
        ":vectorbt_runner_lib",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:pytest",
        "//third_party/python:vectorbt",
    ],
)

py_test(
    name = "test_yaml_strategy_loader",
    size = "medium",
    srcs = ["tests/test_yaml_strategy_loader.py"],
    deps = [
        ":vectorbt_runner_lib",
        ":yaml_strategy_loader_lib",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:pytest",
        "//third_party/python:vectorbt",
    ],
)

py_test(
    name = "test_grpc_tls",
    size = "small",
    srcs = ["tests/test_grpc_tls.py"],
    deps = [
        ":backtesting_service_lib",
        "//third_party/python:grpcio",
    ],
)

py_test(
    name = "test_engine",
    size = "medium",
    srcs = ["tests/test_engine.py"],
    deps = [
        ":engine_lib",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_app",
    size = "medium",
    srcs = ["tests/test_app.py"],
    deps = [
        ":app_lib",
        ":engine_lib",
        ":vectorbt_runner_lib",
        "//third_party/python:fastapi",
        "//third_party/python:numpy",
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
    entrypoint = ["/services/backtesting/app"],
    tars = [":layers"],
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_backtesting_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/backtesting",
)

oci_load(
    name = "load_backtesting_image",
    image = ":image",
    repo_tags = ["backtesting:latest"],
)

filegroup(
    name = "backtesting_tarball",
    srcs = [":load_backtesting_image"],
    output_group = "tarball",
)
