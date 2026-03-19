load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "config_lib",
    srcs = [
        "__init__.py",
        "config.py",
    ],
)

py_library(
    name = "state_lib",
    srcs = ["state.py"],
    deps = [
        ":config_lib",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "discovery_lib",
    srcs = ["discovery.py"],
    deps = [
        ":config_lib",
        "//services/shared:mcp_client",
        "//services/shared:model_config",
        "//third_party/python:absl_py",
        "//third_party/python:openai",
    ],
)

py_library(
    name = "validation_lib",
    srcs = ["validation.py"],
    deps = [
        ":config_lib",
        "//services/shared:mcp_client",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "promotion_lib",
    srcs = ["promotion.py"],
    deps = [
        ":config_lib",
        "//services/shared:mcp_client",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "monitoring_lib",
    srcs = ["monitoring.py"],
    deps = [
        ":config_lib",
        "//services/shared:mcp_client",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "orchestration_loop_lib",
    srcs = ["orchestration_loop.py"],
    deps = [
        ":config_lib",
        ":discovery_lib",
        ":monitoring_lib",
        ":promotion_lib",
        ":state_lib",
        ":validation_lib",
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "dashboard_lib",
    srcs = ["dashboard.py"],
    deps = [
        ":config_lib",
        "//third_party/python:flask",
        "//third_party/python:flask_cors",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":dashboard_lib",
        ":orchestration_loop_lib",
        ":state_lib",
        "//services/shared:structured_logger",
        "//third_party/python:absl_py",
    ],
)

# --- Tests ---

py_test(
    name = "test_config",
    srcs = ["tests/test_config.py"],
    deps = [
        ":config_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_state",
    srcs = ["tests/test_state.py"],
    deps = [
        ":config_lib",
        ":state_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_validation",
    srcs = ["tests/test_validation.py"],
    deps = [
        ":config_lib",
        ":validation_lib",
        "//services/shared:mcp_client",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_promotion",
    srcs = ["tests/test_promotion.py"],
    deps = [
        ":config_lib",
        ":promotion_lib",
        ":state_lib",
        "//services/shared:mcp_client",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_monitoring",
    srcs = ["tests/test_monitoring.py"],
    deps = [
        ":config_lib",
        ":monitoring_lib",
        ":state_lib",
        "//services/shared:mcp_client",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_orchestration_loop",
    srcs = ["tests/test_orchestration_loop.py"],
    deps = [
        ":config_lib",
        ":orchestration_loop_lib",
        ":state_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "test_dashboard",
    srcs = ["tests/test_dashboard.py"],
    deps = [
        ":config_lib",
        ":dashboard_lib",
        ":state_lib",
        "//third_party/python:flask",
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
    entrypoint = ["/services/agent_orchestration/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/agent_orchestration",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_agent_orchestration_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/agent-orchestration",
)

oci_load(
    name = "load_agent_orchestration_image",
    image = ":image",
    repo_tags = ["agent-orchestration:latest"],
)

filegroup(
    name = "agent_orchestration_tarball",
    srcs = [":load_agent_orchestration_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
