load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "retirement_criteria_lib",
    srcs = [
        "__init__.py",
        "retirement_criteria.py",
    ],
    visibility = ["//visibility:public"],
)

py_library(
    name = "db_maintenance_lib",
    srcs = [
        "__init__.py",
        "db_maintenance.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:psycopg2_binary",
    ],
)

py_library(
    name = "health_checker_lib",
    srcs = [
        "__init__.py",
        "health_checker.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "state_repair_lib",
    srcs = [
        "__init__.py",
        "state_repair.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:psycopg2_binary",
    ],
)

py_library(
    name = "scheduler_lib",
    srcs = [
        "__init__.py",
        "scheduler.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "report_lib",
    srcs = [
        "__init__.py",
        "report.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":db_maintenance_lib",
        ":health_checker_lib",
        ":retirement_criteria_lib",
        ":state_repair_lib",
    ],
)

py_library(
    name = "notifier_lib",
    srcs = [
        "__init__.py",
        "notifier.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:requests",
    ],
)

py_library(
    name = "agent_lib",
    srcs = [
        "__init__.py",
        "agent.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        ":db_maintenance_lib",
        ":health_checker_lib",
        ":notifier_lib",
        ":report_lib",
        ":retirement_criteria_lib",
        ":state_repair_lib",
        "//third_party/python:absl_py",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":agent_lib",
        ":scheduler_lib",
        "//third_party/python:absl_py",
    ],
)

# --- Test Targets ---
py_test(
    name = "retirement_criteria_test",
    srcs = ["retirement_criteria_test.py"],
    deps = [
        ":retirement_criteria_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "scheduler_test",
    srcs = ["scheduler_test.py"],
    deps = [
        ":scheduler_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "health_checker_test",
    srcs = ["health_checker_test.py"],
    deps = [
        ":health_checker_lib",
        "//third_party/python:pytest",
        "//third_party/python:requests",
    ],
)

py_test(
    name = "report_test",
    srcs = ["report_test.py"],
    deps = [
        ":report_lib",
        ":retirement_criteria_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "state_repair_test",
    srcs = ["state_repair_test.py"],
    deps = [
        ":state_repair_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "notifier_test",
    srcs = ["notifier_test.py"],
    deps = [
        ":notifier_lib",
        "//third_party/python:pytest",
        "//third_party/python:requests",
    ],
)

py_test(
    name = "agent_test",
    srcs = ["agent_test.py"],
    deps = [
        ":agent_lib",
        ":retirement_criteria_lib",
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
    entrypoint = ["/services/janitor_agent/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/janitor_agent",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_janitor_agent_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/janitor-agent",
)

oci_load(
    name = "load_janitor_agent_image",
    image = ":image",
    repo_tags = ["janitor-agent:latest"],
)

filegroup(
    name = "janitor_agent_tarball",
    srcs = [":load_janitor_agent_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
