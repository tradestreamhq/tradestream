# --- OCI Image Rules ---
load("@aspect_rules_py//py:defs.bzl", "py_image_layer")
load("@container_structure_test//:defs.bzl", "container_structure_test")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_image_index", "oci_push")
load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "strategy_confidence_scorer_lib",
    srcs = ["main.py"],
    deps = [
        "//third_party/python:absl_py",
        "//third_party/python:asyncpg",
    ],
)

py_binary(
    name = "app",
    srcs = ["main.py"],
    main = "main.py",
    deps = [
        ":strategy_confidence_scorer_lib",
    ],
)

# Unit Tests
py_test(
    name = "main_test",
    srcs = ["main_test.py"],
    deps = [
        ":strategy_confidence_scorer_lib",
        "//third_party/python:absl_py",
        "//third_party/python:pytest",
    ],
)

py_image_layer(
    name = "layers",
    binary = ":app",
)

oci_image(
    name = "image",
    base = "@python_3_13_slim",
    entrypoint = ["/services/strategy_confidence_scorer/app"],
    tars = [":layers"],
)

oci_image_index(
    name = "images",
    images = [
        ":image",
    ],
)

oci_push(
    name = "push_strategy_confidence_scorer_image",
    image = ":images",
    repository = "tradestreamhq/strategy-confidence-scorer",
)

container_structure_test(
    name = "container_test",
    configs = ["container-structure-test.yaml"],
    image = ":image",
    tags = ["requires-docker"],
)
