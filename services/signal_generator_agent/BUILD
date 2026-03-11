load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "agent_lib",
    srcs = ["agent.py"],
    deps = [
        "//services/shared:mcp_client",
        "//services/shared:model_config",
        "//third_party/python:absl_py",
        "//third_party/python:openai",
        "//third_party/python:requests",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":agent_lib",
        "//services/shared:structured_logger",
        "//third_party/python:absl_py",
    ],
)

py_test(
    name = "agent_test",
    srcs = ["agent_test.py"],
    args = [],
    deps = [
        ":agent_lib",
        "//services/shared:mcp_client",
        "//services/shared:model_config",
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
    entrypoint = ["/services/signal_generator_agent/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/signal_generator_agent",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_signal_generator_agent_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/signal-generator-agent",
)

oci_load(
    name = "load_signal_generator_agent_image",
    image = ":image",
    repo_tags = ["signal-generator-agent:latest"],
)

filegroup(
    name = "signal_generator_agent_tarball",
    srcs = [":load_signal_generator_agent_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
