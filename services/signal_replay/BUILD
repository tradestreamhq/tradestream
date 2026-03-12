load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

package(default_visibility = ["//visibility:public"])

py_library(
    name = "models_lib",
    srcs = ["models.py"],
)

py_library(
    name = "replayer_lib",
    srcs = ["replayer.py"],
    deps = [
        ":models_lib",
    ],
)

py_test(
    name = "test_replayer",
    size = "small",
    srcs = ["tests/test_replayer.py"],
    deps = [
        ":models_lib",
        ":replayer_lib",
        "//third_party/python:pytest",
    ],
)
