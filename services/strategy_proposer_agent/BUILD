load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "agent_lib",
    srcs = ["agent.py"],
    deps = [
        "//third_party/python:openai",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":agent_lib",
        "//third_party/python:absl_py",
        "//third_party/python:mcp",
    ],
)

py_test(
    name = "agent_test",
    srcs = ["agent_test.py"],
    deps = [
        ":agent_lib",
        "//third_party/python:pytest",
        "//third_party/python:pytest_asyncio",
    ],
)

py_image_layer(
    name = "layers",
    binary = ":app",
)

oci_image(
    name = "image",
    base = "@python_3_13_slim",
    entrypoint = ["/services/strategy_proposer_agent/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/strategy_proposer_agent",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_strategy_proposer_agent_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/strategy-proposer-agent",
)

oci_load(
    name = "load_strategy_proposer_agent_image",
    image = ":image",
    repo_tags = ["strategy-proposer-agent:latest"],
)

filegroup(
    name = "strategy_proposer_agent_tarball",
    srcs = [":load_strategy_proposer_agent_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
