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
    name = "walk_forward_lib",
    srcs = ["walk_forward.py"],
    deps = [
        ":vectorbt_runner_lib",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
    ],
)

py_library(
    name = "monte_carlo_lib",
    srcs = ["monte_carlo.py"],
    deps = [
        ":vectorbt_runner_lib",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:vectorbt",
    ],
)

py_library(
    name = "portfolio_backtest_lib",
    srcs = ["portfolio_backtest.py"],
    deps = [
        ":vectorbt_runner_lib",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:vectorbt",
    ],
)

py_library(
    name = "results_comparison_lib",
    srcs = ["results_comparison.py"],
    deps = [
        ":vectorbt_runner_lib",
    ],
)

py_library(
    name = "backtesting_service_lib",
    srcs = ["backtesting_service.py"],
    deps = [
        ":monte_carlo_lib",
        ":portfolio_backtest_lib",
        ":vectorbt_runner_lib",
        ":walk_forward_lib",
        "//protos:backtesting_py_proto",
        "//protos:marketdata_py_proto",
        "//protos:strategies_py_proto",
        "//services/shared:strategy_parameter_registry",
        "//third_party/python:grpcio",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
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
    name = "test_walk_forward",
    size = "medium",
    srcs = ["tests/test_walk_forward.py"],
    deps = [
        ":vectorbt_runner_lib",
        ":walk_forward_lib",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:pytest",
        "//third_party/python:vectorbt",
    ],
)

py_test(
    name = "test_monte_carlo",
    size = "medium",
    srcs = ["tests/test_monte_carlo.py"],
    deps = [
        ":monte_carlo_lib",
        ":vectorbt_runner_lib",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:pytest",
        "//third_party/python:vectorbt",
    ],
)

py_test(
    name = "test_portfolio_backtest",
    size = "medium",
    srcs = ["tests/test_portfolio_backtest.py"],
    deps = [
        ":portfolio_backtest_lib",
        ":vectorbt_runner_lib",
        "//third_party/python:numpy",
        "//third_party/python:pandas",
        "//third_party/python:pytest",
        "//third_party/python:vectorbt",
    ],
)

py_test(
    name = "test_results_comparison",
    size = "small",
    srcs = ["tests/test_results_comparison.py"],
    deps = [
        ":results_comparison_lib",
        ":vectorbt_runner_lib",
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
