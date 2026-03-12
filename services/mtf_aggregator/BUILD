load("@rules_python//python:defs.bzl", "py_library", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "mtf_aggregator_models",
    srcs = ["models.py"],
)

py_library(
    name = "mtf_aggregator_lib",
    srcs = ["aggregator.py"],
    deps = [
        ":mtf_aggregator_models",
    ],
)

py_test(
    name = "aggregator_test",
    srcs = ["aggregator_test.py"],
    deps = [
        ":mtf_aggregator_lib",
        ":mtf_aggregator_models",
        "//third_party/python:pytest",
    ],
)
