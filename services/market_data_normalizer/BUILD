load("@rules_python//python:py_library.bzl", "py_library")
load("@rules_python//python:py_test.bzl", "py_test")

py_library(
    name = "normalizer_lib",
    srcs = [
        "__init__.py",
        "normalizer.py",
    ],
    visibility = ["//visibility:public"],
)

py_test(
    name = "normalizer_test",
    srcs = ["normalizer_test.py"],
    deps = [
        ":normalizer_lib",
        "//third_party/python:pytest",
    ],
)
