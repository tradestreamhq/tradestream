load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_load", "oci_push")
load("@rules_python//python:py_binary.bzl", "py_binary")
load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "engine_lib",
    srcs = ["engine.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:psycopg2_binary",
    ],
)

py_library(
    name = "regime_detector_lib",
    srcs = ["regime_detector.py"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "performance_tracker_lib",
    srcs = ["performance_tracker.py"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "weight_optimizer_lib",
    srcs = ["weight_optimizer.py"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "parameter_adapter_lib",
    srcs = ["parameter_adapter.py"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "regime_alerter_lib",
    srcs = ["regime_alerter.py"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "dashboard_provider_lib",
    srcs = ["dashboard_provider.py"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_library(
    name = "ab_testing_lib",
    srcs = ["ab_testing.py"],
    deps = [
        "//third_party/python:absl_py",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":ab_testing_lib",
        ":dashboard_provider_lib",
        ":engine_lib",
        ":parameter_adapter_lib",
        ":performance_tracker_lib",
        ":regime_alerter_lib",
        ":regime_detector_lib",
        ":weight_optimizer_lib",
        "//services/shared:structured_logger",
        "//third_party/python:absl_py",
        "//third_party/python:psycopg2_binary",
    ],
)

py_test(
    name = "engine_test",
    srcs = ["engine_test.py"],
    args = [],
    deps = [
        ":engine_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "regime_detector_test",
    srcs = ["regime_detector_test.py"],
    args = [],
    deps = [
        ":regime_detector_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "performance_tracker_test",
    srcs = ["performance_tracker_test.py"],
    args = [],
    deps = [
        ":performance_tracker_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "weight_optimizer_test",
    srcs = ["weight_optimizer_test.py"],
    args = [],
    deps = [
        ":weight_optimizer_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "parameter_adapter_test",
    srcs = ["parameter_adapter_test.py"],
    args = [],
    deps = [
        ":parameter_adapter_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "regime_alerter_test",
    srcs = ["regime_alerter_test.py"],
    args = [],
    deps = [
        ":regime_alerter_lib",
        "//third_party/python:pytest",
    ],
)

py_test(
    name = "ab_testing_test",
    srcs = ["ab_testing_test.py"],
    args = [],
    deps = [
        ":ab_testing_lib",
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
    entrypoint = ["/services/learning_engine/app"],
    tars = [":layers"],
    user = "nobody",
    workdir = "/services/learning_engine",
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_learning_engine_image",
    image = ":images",
    repository = "ghcr.io/tradestreamhq/learning-engine",
)

oci_load(
    name = "load_learning_engine_image",
    image = ":image",
    repo_tags = ["learning-engine:latest"],
)

filegroup(
    name = "learning_engine_tarball",
    srcs = [":load_learning_engine_image"],
    output_group = "tarball",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
