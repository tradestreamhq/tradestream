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
    name = "retry_handler_lib",
    srcs = ["retry_handler.py"],
    deps = [
        ":config_lib",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "health_monitor_lib",
    srcs = ["health_monitor.py"],
    deps = [
        ":config_lib",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "scheduler_lib",
    srcs = ["scheduler.py"],
    deps = [
        ":config_lib",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "orchestrator_lib",
    srcs = ["orchestrator.py"],
    deps = [
        ":config_lib",
        ":health_monitor_lib",
        ":retry_handler_lib",
        ":scheduler_lib",
        "//services/shared:mcp_client",
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":health_monitor_lib",
        ":orchestrator_lib",
        ":scheduler_lib",
        "//third_party/python:absl_py",
    ],
)

py_test(
    name = "test_config",
    srcs = ["tests/test_config.py"],
    deps = [
        ":config_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_retry_handler",
    srcs = ["tests/test_retry_handler.py"],
    deps = [
        ":config_lib",
        ":retry_handler_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_health_monitor",
    srcs = ["tests/test_health_monitor.py"],
    deps = [
        ":config_lib",
        ":health_monitor_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_scheduler",
    srcs = ["tests/test_scheduler.py"],
    deps = [
        ":scheduler_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_orchestrator",
    srcs = ["tests/test_orchestrator.py"],
    deps = [
        ":config_lib",
        ":health_monitor_lib",
        ":orchestrator_lib",
        ":scheduler_lib",
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
    entrypoint = ["/services/orchestrator_agent/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/orchestrator_agent",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_orchestrator_agent_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/orchestrator-agent",
)

oci_load(
    name = "load_orchestrator_agent_image",
    image = ":image",
    repo_tags = ["orchestrator-agent:latest"],
)

filegroup(
    name = "orchestrator_agent_tarball",
    srcs = [":load_orchestrator_agent_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
